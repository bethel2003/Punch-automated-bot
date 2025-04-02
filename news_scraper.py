import os
import smtplib
import base64
import requests
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from transformers import pipeline

# ==============================
# ✅ 1. SCRAPE NEWS FROM PUNCH
# ==============================
def scrape_punch_news():
    url = "https://punchng.com/"  # Punch Newspaper homepage
    response = requests.get(url)
    
    if response.status_code != 200:
        print("Error: Could not access Punch Newspaper")
        return None, None, None

    soup = BeautifulSoup(response.text, "html.parser")
    
    # Automatically find first news article
    first_article = soup.find("article")
    if not first_article:
        print("Error: Could not find news article")
        return None, None, None
    
    # Extract headline
    headline = first_article.find("h2").get_text(strip=True)
    
    # Extract article link
    article_url = first_article.find("a")["href"]
    if not article_url.startswith("http"):
        article_url = f"https://punchng.com{article_url}"
    
    # Fetch full article
    article_response = requests.get(article_url)
    article_soup = BeautifulSoup(article_response.text, "html.parser")
    
    # Extract article content
    paragraphs = article_soup.find_all("p")
    article_body = "\n".join([p.get_text(strip=True) for p in paragraphs])
    
    # Extract image URL
    image_tag = article_soup.find("img")
    image_url = image_tag["src"] if image_tag else None
    
    return headline, article_body, image_url

# ==============================
# ✅ 2. REWRITE ARTICLE
# ==============================
def rewrite_article(text):
    paraphraser = pipeline("text2text-generation", model="humarin/chatgpt_paraphraser_on_T5_base")
    rewritten_text = paraphraser(text, max_length=500)[0]['generated_text']
    return rewritten_text

# ==============================
# ✅ 3. HANDLE IMAGE (URL & BASE64)
# ==============================
def download_image(image_url):
    if not image_url:
        print("No image found for this article.")
        return None

    if image_url.startswith("data:image"):
        # Handle Base64 encoded images
        base64_str = image_url.split(",", 1)[1]
        image_data = base64.b64decode(base64_str)
        image = Image.open(BytesIO(image_data))
        image_path = "article_image.png"
        image.save(image_path)
    else:
        # Handle regular image URLs
        response = requests.get(image_url)
        if response.status_code == 200:
            image_path = "article_image.png"
            with open(image_path, "wb") as f:
                f.write(response.content)
        else:
            print("Failed to download image")
            return None
    return image_path

# ==============================
# ✅ 4. SEND EMAIL
# ==============================
def send_email(subject, body, image_path):
    EMAIL_SENDER = os.getenv("EMAIL_SENDER")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")  # Use Google App Password
    EMAIL_RECIPIENT = os.getenv("EMAIL_RECIPIENT")

    msg = MIMEMultipart()
    msg["From"] = EMAIL_SENDER
    msg["To"] = EMAIL_RECIPIENT
    msg["Subject"] = subject
    
    msg.attach(MIMEText(body, "plain"))

    if image_path:
        with open(image_path, "rb") as attachment:
            mime_part = MIMEBase("application", "octet-stream")
            mime_part.set_payload(attachment.read())
            encoders.encode_base64(mime_part)
            mime_part.add_header("Content-Disposition", f"attachment; filename={image_path}")
            msg.attach(mime_part)

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECIPIENT, msg.as_string())
        server.quit()
        print("✅ Email sent successfully!")
    except Exception as e:
        print(f"❌ Error sending email: {e}")

# ==============================
# ✅ 5. MAIN EXECUTION
# ==============================
if __name__ == "__main__":
    headline, article_body, image_url = scrape_punch_news()

    if headline and article_body:
        print(f"📰 Scraped Article: {headline}")
        rewritten_article = rewrite_article(article_body)
        image_path = download_image(image_url)

        send_email(headline, rewritten_article, image_path)
    else:
        print("❌ Failed to retrieve news article.")
