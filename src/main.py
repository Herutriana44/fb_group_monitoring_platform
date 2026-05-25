import asyncio
import logging
import argparse
from auth import login
from collector import GroupCollector
from processor import PostProcessor
from notifier import Notifier

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Facebook Group Monitor CLI")
    parser.add_argument('--action', choices=['login', 'monitor'], required=True, help="Action to perform")
    parser.add_argument('--user', help="Facebook email")
    parser.add_argument('--pass', dest='password', help="Facebook password")
    
    args = parser.parse_args()

    if args.action == 'login':
        if not args.user or not args.password:
            logger.error("Username and password are required for login.")
            return
        await login(args.user, args.password)
    elif args.action == 'monitor':
        logger.info("Starting monitoring process...")
        collector = GroupCollector(group_id="YOUR_GROUP_ID")
        processor = PostProcessor(keywords=["lelang", "jual"])
        notifier = Notifier()
        
        posts = await collector.fetch_feed()
        matches = processor.process_posts(posts)
        
        for match in matches:
            notifier.notify(f"Match found: {match[:100]}...")
        
        logger.info("Monitoring finished.")

if __name__ == "__main__":
    asyncio.run(main())
