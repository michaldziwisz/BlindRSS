
import unittest
import sys
import os
sys.path.append(os.getcwd())
from core import article_extractor

class TestBoilerplateRemoval(unittest.TestCase):
    def test_9to5mac(self):
        text = """
FTC: We use income earning auto affiliate links. More.
You’re reading 9to5Mac — experts who break news about Apple and its surrounding ecosystem, day after day. Be sure to check out our homepage for all the latest news, and follow 9to5Mac on Twitter, Facebook, and LinkedIn to stay in the loop. Don’t know where to start? Check out our exclusive stories, reviews, how-tos, and subscribe to our YouTube channelRyan got his start in journalism as an Editor at MacStories...
Real Content Here.
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "https://9to5mac.com/some-article")
        self.assertNotIn("FTC: We use", cleaned)
        self.assertNotIn("You’re reading 9to5Mac", cleaned)
        self.assertNotIn("subscribe to our YouTube channel", cleaned)
        self.assertIn("Real Content Here", cleaned)
        # "Ryan got his start..." might remain as it was appended to the boilerplate in the user example without newline.
        # My regex handles "subscribe to our YouTube channel" which precedes "Ryan".
        
    def test_globalnews(self):
        text = """
By Staff The Canadian Press
Posted December 31, 2025 5:28 pm
1 min read
If you get Global News from Instagram or Facebook - that will be changing. Find out how you can still connect with us.
Hide message barDescrease article font size
Increase article font size
Real Article Content.
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "https://globalnews.ca/news/123")
        self.assertNotIn("By Staff", cleaned)
        self.assertNotIn("Posted December", cleaned)
        self.assertNotIn("1 min read", cleaned)
        self.assertNotIn("If you get Global News", cleaned)
        self.assertNotIn("Hide message bar", cleaned)
        self.assertIn("Real Article Content", cleaned)

    def test_aljazeera(self):
        text = """
Published On 6 Jan 20266 Jan 2026
Click here to share on social media
share2Save
Real Content.
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "https://www.aljazeera.com/news")
        self.assertNotIn("Published On", cleaned)
        self.assertNotIn("Click here to share", cleaned)
        self.assertNotIn("share2Save", cleaned)
        self.assertIn("Real Content", cleaned)

    def test_bbc(self):
        text = """
ShareSave
Ana Faguyon Capitol Hill
ShareSave
Real Content.
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "https://www.bbc.com/news/articles/cgl8y4gx9lyo")
        self.assertNotIn("ShareSave", cleaned)
        self.assertIn("Real Content", cleaned)

    def test_canada(self):
        text = """
Advertisement 1
This advertisement has not loaded yet, but your article continues below.
Author of the article:
Randi MannPublished Jan 06, 2026 • 6 minute read
Join the conversation
Real Content.
Read More
African safari: Sleep under the stars...
Article content
Share this article in your social network
Trending
Latest National Stories
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "https://o.canada.com/travel")
        self.assertNotIn("Advertisement 1", cleaned)
        self.assertNotIn("This advertisement has not loaded", cleaned)
        self.assertNotIn("Author of the article", cleaned)
        self.assertNotIn("Join the conversation", cleaned)
        self.assertNotIn("Read More", cleaned)
        self.assertNotIn("Trending", cleaned)
        self.assertIn("Real Content", cleaned)

    def test_castanet(self):
        text = """
- Child killed by three dogsNova Scotia - 10:07 am
- Urged to approve a pipelineCanada - 10:04 am
Real Content.
"""
        cleaned = article_extractor._postprocess_extracted_text(text, "http://www.castanet.net/rss/page-3.xml")
        self.assertNotIn("Child killed by three dogs", cleaned)
        self.assertIn("Real Content", cleaned)

if __name__ == '__main__':
    unittest.main()
