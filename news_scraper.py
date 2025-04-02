import os
import requests
import smtplib
import base64
from bs4 import BeautifulSoup
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from PIL import Image
from io import BytesIO
from transformers import pipeline

# ==============================
# ✅ EMAIL CONFIGURATION
# ==============================
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = os.getenv("EMAIL_SENDER")  # Use environment variables
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

# ==============================
# ✅ BASE URL
# ==============================
PUNCH_NEWS_URL = "https://punchng.com/"

# ==============================
# ✅ LOAD TRANSFORMER MODEL
# ==============================
paraphrase_model = pipeline("text2text-generation", model="humarin/chatgpt_paraphraser_on_T5_base")


# ==============================
# ✅ SCRAPE THE LATEST ARTICLE
# ==============================
def get_latest_article():
    """Scrapes the latest article from Punch Newspaper."""
    try:
        response = requests.get(PUNCH_NEWS_URL, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Find latest article dynamically
        latest_article = soup.find("article")
        if not latest_article:
            raise Exception("No article found on the homepage.")

        link = latest_article.find("a")["href"]
        article_url = link if "http" in link else PUNCH_NEWS_URL + link

        return extract_article_details(article_url)

    except Exception as e:
        print(f"❌ Error getting latest article: {e}")
        return None


# ==============================
# ✅ EXTRACT ARTICLE DETAILS
# ==============================
def extract_article_details(article_url):
    """Extracts article details including headline, content, and image."""
    try:
        response = requests.get(article_url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract headline
        headline = soup.find("h1").text.strip()

        # Extract article content
        paragraphs = soup.find_all("p")
        article_body = "\n".join(p.text.strip() for p in paragraphs if len(p.text.strip()) > 50)

        # Extract image URL
        image_tag = soup.find("img")
        image_url = image_tag["src"] if image_tag else None

        return {"headline": headline, "body": article_body, "image_url": image_url}

    except Exception as e:
        print(f"❌ Error extracting article details: {e}")
        return None


# ==============================
# ✅ REWRITE ARTICLE
# ==============================
def rewrite_text(text):
    """Uses a Transformers model to paraphrase the extracted text."""
    try:
        rewritten = paraphrase_model(f"paraphrase: {text}", max_length=512, truncation=True)
        return rewritten[0]['generated_text']
    except Exception as e:
        print(f"❌ Error rewriting article: {e}")
        return text


# ==============================
# ✅ DOWNLOAD IMAGE (URL & BASE64)
# ==============================
def download_image(image_url):
    """Downloads and saves the article's featured image."""
    if not image_url:
        return None

    try:
        if image_url.startswith("data:image"):
            # Handle Base64 encoded images
            base64_str = image_url.split(",", 1)[1]
            image_data = base64.b64decode(base64_str)
            image = Image.open(BytesIO(image_data))
        else:
            # Download regular image
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            image = Image.open(BytesIO(response.content))

        # Validate image format
        if image.format not in ["JPEG", "PNG", "WEBP"]:
            print("❌ Invalid image format detected!")
            return None

        image_path = "article_image.png"
        image.save(image_path)
        return image_path

    except Exception as e:
        print(f"❌ Error downloading image: {e}")
        return None


# ==============================
# ✅ SEND EMAIL WITH ARTICLE & IMAGE
# ==============================
def send_email(subject, body, image_path=None):
    """Sends the rewritten article via email with the image attached."""
    try:
        msg = MIMEMultipart()
        msg["From"] = EMAIL_SENDER
        msg["To"] = EMAIL_RECIPIENT
        msg["Subject"] = subject

        msg.attach(MIMEText(body, "plain"))

        if image_path:
            with open(image_path, "rb") as attachment:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename={os.path.basename(image_path)}")
                msg.attach(part)

        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)

        # ✅ FIXED: Ensure msg is properly encoded before sending
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string().encode("utf-8"))
        
        server.quit()
        print("✅ Email sent successfully!")

    except Exception as e:
        print(f"❌ Error sending email: {e}")


# ==============================
# ✅ MAIN EXECUTION
# ==============================
def main():
    """Main execution flow."""
    article = get_latest_article()
    if not article:
        print("❌ Failed to retrieve the latest article.")
        return

    rewritten_text = rewrite_text(article["body"])
    image_path = download_image(article["image_url"])

    send_email(subject=article["headline"], body=rewritten_text, image_path=image_path)


if __name__ == "__main__":
    main()
