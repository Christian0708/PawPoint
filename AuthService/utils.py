import bcrypt
import random
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from params import from_email, app_password

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), 
                         bcrypt.gensalt()).decode('utf-8')

def generate_otp():
    return str(random.randint(100000, 999999))

def send_otp(to_email) -> str:

    otp = generate_otp()

    # Sender configuration
    subject = "Your OTP Code for the cloud security simulator"
    body = f"Your OTP code is: {otp}"

    # Create the email
    msg = MIMEMultipart()
    email_from = os.getenv('CLOUD_EMAIL_FROM', from_email)
    email_pass = os.getenv('CLOUD_EMAIL_PASS', app_password)
    msg['From'] = email_from
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Connect and send email with timeout
        server = smtplib.SMTP('smtp.gmail.com', 587, timeout=5)
        try:
            print(f"Starting tls session on smtp.gmail.com:587 .........", end='')
            server.starttls()  # Upgrade the connection to a secure encrypted SSL/TLS connection
            print('[OK]')
            print(f"login to the server with {email_from} .........", end='')
            server.login(email_from, email_pass)
            print('[OK]')
            print(f"Sending OTP data to {to_email}  .........", end='')
            server.send_message(msg)
            print('[OK]')
            print(f"OTP data sent to {to_email} successfully!")
            return f"OTP data sent to your email: {to_email} successfully!"
        finally:
            server.quit()
    except Exception as e:
        print(f"Failed to send email: {e}")
        # Return None or empty string to indicate failure, but don't block
        return None

if __name__ == '__main__':
    base_dir = os.path.dirname(__file__)
    entries = []
    ids_path = os.path.join(base_dir, 'ids')
    with open(ids_path, 'r') as file:
        for line in file:
            parts = line.strip().split(',')
            if len(parts) == 3:
                username, email, password = parts
            elif len(parts) == 2:
                username, password = parts
                email = f"{username}@example.com"
            else:
                continue
            entries.append((username, email, password))

    credentials_path = os.path.join(base_dir, 'credentials')
    with open(credentials_path, 'w') as file:
        for username, email, password in entries:
            file.write(f'{username},{email},{hash_password(password)}\n')
