import smtplib
from email.mime.text import MIMEText
import json

def send_alert(message):
    with open("config.json", "r") as f:
        config = json.load(f)
    
    sender_email = config["sender_email"]
    sender_password = config["sender_password"]
    recipients = config["recipients"]
    
    msg = MIMEText(message)
    msg['Subject'] = "Fall Detection Alert"
    msg['From'] = sender_email
    msg['To'] = ", ".join(recipients)
    
    try:
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, recipients, msg.as_string())
        server.quit()
        print("Alert sent successfully!")
    except Exception as e:
        print(f"Failed to send alert: {e}")