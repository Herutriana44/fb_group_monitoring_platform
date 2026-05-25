import logging

logger = logging.getLogger(__name__)

class PostProcessor:
    def __init__(self, keywords):
        self.keywords = keywords

    def process_posts(self, posts):
        logger.info(f"Processing {len(posts)} posts...")
        filtered_posts = []
        for post in posts:
            if any(keyword.lower() in post.lower() for keyword in self.keywords):
                filtered_posts.append(post)
        logger.info(f"Found {len(filtered_posts)} matching posts.")
        return filtered_posts
