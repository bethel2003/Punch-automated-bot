import requests
from bs4 import BeautifulSoup
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from urllib.parse import urljoin
from transformers import T5ForConditionalGeneration, T5Tokenizer

# Set up logging
logging.basicConfig(level=logging.INFO)

# Email Configuration
SENDER_EMAIL = "bethelisrael20030629@gmail.com"  # Replace with your email
SENDER_PASSWORD = "zhrbbcpugxffskfg"  # Replace with your App Password
BLOGGER_EMAIL = "betlognewspapers.2000@blogger.com"  # Blogger's unique posting email

# Load T5 model and tokenizer for paraphrasing
logging.info("Loading T5 model and tokenizer...")
tokenizer = T5Tokenizer.from_pretrained("t5-small")
model = T5ForConditionalGeneration.from_pretrained("t5-small")
logging.info("T5 model and tokenizer loaded successfully.")

# Set to track processed article URLs
processed_articles = set()

# Function to paraphrase text using T5
def paraphrase_text(text):
    try:
        if not text or text.strip() == "":
            return text

        # Prepare input for T5
        input_text = f"paraphrase: {text}"
        input_ids = tokenizer.encode(input_text, return_tensors="pt", max_length=512, truncation=True)

        # Generate paraphrased text
        outputs = model.generate(
            input_ids,
            max_length=512,
            num_beams=5,
            num_return_sequences=1,
            temperature=0.7,
        )

        paraphrased_content = tokenizer.decode(outputs[0], skip_special_tokens=True)
        return paraphrased_content
    except Exception as e:
        logging.error(f"Error paraphrasing text with T5: {e}")
        return text  # Return original text if paraphrasing fails

# Function to fetch articles from Punch Newspaper
def fetch_punch_articles():
    try:
        logging.info("Fetching articles from Punch Newspaper...")
        url = 'https://punchng.com/'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        logging.info(f"Response Status Code: {response.status_code}")
        
        soup = BeautifulSoup(response.content, 'html.parser')
        articles = []
        
        # Fetch articles with proper selectors
        for item in soup.find_all('h2')[:10]:  # Limit to 10 articles
            a_tag = item.find('a')
            if a_tag and a_tag['href']:
                article_url = urljoin(url, a_tag['href'])  # Ensure the URL is absolute
                if article_url not in processed_articles:  # Skip processed articles
                    articles.append(article_url)
                    processed_articles.add(article_url)  # Mark as processed

        logging.info(f"Fetched {len(articles)} new articles.")
        return articles
    except requests.RequestException as e:
        logging.error(f"Error fetching articles: {e}")
        return []

# Function to fetch article content and image
def get_article_content(link):
    try:
        logging.info(f"Fetching content from article: {link}")
        response = requests.get(link)
        response.raise_for_status()
        article_soup = BeautifulSoup(response.content, 'html.parser')

        # Extract title
        title_tag = article_soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else "⚠️ Title Not Found"

        # Extract article content
        content_tag = article_soup.find('div', class_='entry-content') or article_soup.find('article')
        if content_tag:
            paragraphs = content_tag.find_all('p')
            # Remove duplicate paragraphs
            unique_paragraphs = []
            seen = set()
            for p in paragraphs:
                text = p.get_text(strip=True)
                if text and text not in seen:  # Avoid duplicates and empty paragraphs
                    seen.add(text)
                    unique_paragraphs.append(f"<p>{text}</p>")
            content = "\n".join(unique_paragraphs)  # Join unique paragraphs
        else:
            content = "<p>⚠️ Content Not Found</p>"

        # Paraphrase the content using T5
        logging.info("Paraphrasing content...")
        paraphrased_content = paraphrase_text(content)

        # Extract the first image within the article content
        image_url = None
        if content_tag:
            # Look for images within the article content
            image_tag = content_tag.find('img', {'src': True})
            if image_tag:
                image_url = urljoin(link, image_tag['src'])  # Ensure the image URL is absolute

            # Check for lazy-loaded images
            if not image_url:
                lazy_image_tag = content_tag.find('img', {'data-src': True})
                if lazy_image_tag:
                    image_url = urljoin(link, lazy_image_tag['data-src'])

        logging.info(f"Title: {title}")
        logging.info(f"Original Content: {content[:1000]}...")  # Log the first 1000 characters of the original content
        logging.info(f"Paraphrased Content: {paraphrased_content[:1000]}...")  # Log the first 1000 characters of the paraphrased content
        logging.info(f"Image URL: {image_url}")

        return title, paraphrased_content, image_url
    except requests.RequestException as e:
        logging.error(f"Error fetching article content from {link}: {e}")
        return None, None, None

# Function to send email to Blogger
def send_email_to_blogger(title, content, image_url):
    try:
        logging.info("Sending email to Blogger...")
        email_content = f"<h2>{title}</h2>{content}"  # Content already includes <p> tags

        if image_url:
            email_content = f"<img src='{image_url}' width='600'><br>" + email_content

        msg = MIMEMultipart()
        msg["From"] = SENDER_EMAIL
        msg["To"] = BLOGGER_EMAIL
        msg["Subject"] = title
        msg.attach(MIMEText(email_content, "html"))

        context = ssl.create_default_context()
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, context=context) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, BLOGGER_EMAIL, msg.as_string())
            logging.info("Email sent successfully.")
    except Exception as e:
        logging.error(f"Error sending email: {e}")

# Main function to coordinate fetching articles and sending them via email
def main():
    logging.info("Starting script...")
    articles = fetch_punch_articles()
    for article_url in articles:
        title, content, image_url = get_article_content(article_url)
        if title and content:
            send_email_to_blogger(title, content, image_url)
    logging.info("Script execution completed.")

if __name__ == "__main__":
    main()
