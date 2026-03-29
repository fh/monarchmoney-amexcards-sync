import argparse
import csv
import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from monarchmoney import MonarchMoney, RequireMFAException

load_dotenv()

async def get_or_create_tag(mm, tag_name, tag_cache):
    if tag_name in tag_cache:
        return tag_cache[tag_name]

    # Fetch existing tags
    tags_res = await mm.get_transaction_tags()
    tags = tags_res.get('householdTransactionTags', [])
    for t in tags:
        if t['name'] == tag_name:
            tag_cache[tag_name] = t['id']
            return t['id']

    # Create tag if it doesn't exist
    print(f"Creating missing tag in Monarch: {tag_name}")
    # Color can be yellow/blue/red etc.
    new_tag_res = await mm.create_transaction_tag(name=tag_name, color="blue")
    
    try:
        new_tag = new_tag_res['createTransactionTag']['tag']
        tag_cache[tag_name] = new_tag['id']
        return new_tag['id']
    except (KeyError, TypeError) as e:
        print(f"Error creating tag {tag_name}: {new_tag_res}")
        return None

async def main():
    parser = argparse.ArgumentParser(description="Sync Amex CSV to Monarch Tags")
    parser.add_argument("csv_file", help="Path to the Amex activity.csv")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying Monarch data")
    args = parser.parse_args()

    # Read CSV
    print(f"Reading Amex CSV: {args.csv_file}")
    amex_txs = []
    with open(args.csv_file, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('Date') or not row.get('Amount'):
                continue
                
            try:
                date_obj = datetime.strptime(row['Date'], '%m/%d/%Y').date()
                amount = float(row['Amount'])
            except ValueError:
                continue

            card_member = row.get('Card Member', '').strip()
            if not card_member:
                continue
                
            # Use title case for a nicer tag name (e.g. "Amex Florian M Holzhauer")
            tag_name = f"Amex {card_member.title()}"
            amex_txs.append({
                'date': date_obj,
                'amount': amount,
                'description': row.get('Description', ''),
                'tag_name': tag_name,
                'used': False
            })

    print(f"Loaded {len(amex_txs)} expense/payment transactions from CSV.")

    # Authenticate with Monarch using interactive login
    print("Authenticating with Monarch (interactive mode)...")
    # Increase GraphQL network timeout from default 10s to 30s
    mm = MonarchMoney(timeout=30)
    
    # This will prompt for Email, Password, and MFA code if needed, 
    # and automatically save/load the session in the .mm folder.
    await mm.interactive_login()
    print("Successfully authenticated.")

    # Fetch Monarch transactions
    print("Fetching Monarch transactions... (This may take a moment)")
    # limit=2000 should cover recent history; could be paginated/searched by date if needed.
    monarch_res = await mm.get_transactions(limit=3000)
    monarch_transactions = monarch_res.get('allTransactions', {}).get('results', [])
    print(f"Loaded {len(monarch_transactions)} transactions from Monarch.")

    tag_cache = {}
    matches = []

    # Matching Logic
    # Monarch amounts are typically negative for expenses. Amex CSV has expenses as positive.
    for m_tx in monarch_transactions:
        # Monarch date format: '2026-03-05'
        try:
            m_date = datetime.strptime(m_tx['date'], '%Y-%m-%d').date()
        except KeyError:
            continue
            
        m_amount = float(m_tx['amount'])
        m_id = m_tx['id']
        m_tags = [t['id'] for t in m_tx.get('tags', [])]
        m_merchant = m_tx.get('merchant', {}).get('name', '') if m_tx.get('merchant') else ''

        # Find candidate in Amex
        for a_tx in amex_txs:
            if a_tx['used']:
                continue
                
            # Amex amount is positive for expenses, Monarch is negative.
            # So a $74.02 Amex expense is -74.02 in Monarch.
            # Amex payment is -4930.45, Monarch might be +4930.45 (or ignored since it's a transfer)
            if abs(m_amount + a_tx['amount']) < 0.01:
                # Check date within +/- 4 days (to account for posting delays)
                date_diff = abs((m_date - a_tx['date']).days)
                if date_diff <= 4:
                    # Match found
                    a_tx['used'] = True
                    matches.append((m_tx, a_tx))
                    break

    print(f"Found {len(matches)} matching transactions between Monarch and Amex.")

    if not matches:
        print("No transactions matched. Exiting.")
        return

    # Apply Tags
    applied_count = 0
    for m_tx, a_tx in matches:
        tag_name = a_tx['tag_name']
        m_id = m_tx['id']
        m_tags = [t['id'] for t in m_tx.get('tags', [])]
        
        tag_id = await get_or_create_tag(mm, tag_name, tag_cache)
        if not tag_id:
            continue
            
        if tag_id in m_tags:
            # Already tagged
            continue

        m_date = m_tx['date']
        m_amount = m_tx['amount']
        merchant_name = m_tx.get('merchant', {}).get('name', 'Unknown')
        
        print(f"Match: Monarch ({m_date} | {merchant_name} | ${m_amount}) <-> Amex ({a_tx['date']} | ${a_tx['amount']}) => Tagging with '{tag_name}'")
        
        if args.dry_run:
            print(f"  [DRY RUN] Would tag transaction {m_id} with {tag_name}")
            applied_count += 1
        else:
            m_tags.append(tag_id)
            await mm.set_transaction_tags(transaction_id=m_id, tag_ids=m_tags)
            print(f"  [SUCCESS] Tagged {m_id} with {tag_name}")
            applied_count += 1
            await asyncio.sleep(1.0) # Rate limiting to prevent Monarch blocking us

    print(f"Finished processing! Applied {applied_count} tags.{' (DRY RUN)' if args.dry_run else ''}")

    # Debug reporting for unmatched Amex transactions
    unmatched_amex = [t for t in amex_txs if not t['used']]
    if unmatched_amex:
        print(f"\n[DEBUG] {len(unmatched_amex)} Amex transactions were not found in Monarch:")
        for t in unmatched_amex[:10]:
            print(f"  - {t['date']} | ${t['amount']} | {t['description']}")
        if len(unmatched_amex) > 10:
            print(f"  ... and {len(unmatched_amex) - 10} more. Check if the dates or exact amounts differ in Monarch!")

if __name__ == '__main__':
    asyncio.run(main())
