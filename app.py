from flask import send_file
from flask import Flask, request, jsonify, make_response
import email.header
import imaplib
import email
import json
import re
import pytz
import os
import base64

app = Flask(__name__)

@app.route('/search', methods=['POST'])
def search():
    # Set the time zone to IST
    ist = pytz.timezone('Asia/Kolkata')

    #accepting the data
    data = request.get_json()
    username = data['email']
    password = data['password']
    keyword = data['keyword']
    
    # IMAP settings for Gmail
    imap_host = 'imap.gmail.com'
    imap_port = 993

    # Connect to the Gmail server using IMAP
        # Connect to the Gmail server using IMAP
    try:
        imap_server = imaplib.IMAP4_SSL(imap_host, imap_port)
        imap_server.login(username, password)
        imap_server.select('inbox')
    except imaplib.IMAP4.error:
        return "Invalid email or password", 401

    # Search for emails containing the keyword
    status, message_ids = imap_server.search(None, f'BODY "{keyword}"')

    # Process each email that contains the keyword
    emails = []
    for message_id in message_ids[0].split():
        _, msg = imap_server.fetch(message_id, '(RFC822)')
        email_message = email.message_from_bytes(msg[0][1])
        email_date = email_message['Date']
        datetime_obj = email.utils.parsedate_to_datetime(
            email_date).astimezone(ist)
        datetime = datetime_obj.strftime('%Y-%m-%d %H:%M:%S')
        thread_count = email_message['X-Gmail-Thread-Count']
        email_from = email_message['From']
        email_from = re.findall(r'<(.+?)>', email_from)
        if(len(email_from) > 0):
            email_from = email_from[0]
        else:
            email_from = ""
        email_to = email_message['To']
        pattern = r'[\w\.-]+@[\w\.-]+'
        email_to = re.findall(pattern, email_to)
        email_to = set(email_to)
        email_to = ', '.join(email_to)
        subject = email_message['Subject']
        decoded = []

        for s, encoding in email.header.decode_header(subject):
            if isinstance(s, bytes):
                s = s.decode(encoding or "utf-8", errors="replace")
            decoded.append(s)

        decoded_header = ''.join(decoded)
        subject = decoded_header

        # Extract email attachments
        attachments = []
        for part in email_message.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            filename = part.get_filename()
            attachment_id = part.get('Content-ID')
            attachment = {
                'filename': filename,
                'data': base64.b64encode(part.get_payload(decode=True)).decode(),
                'content_type': part.get_content_type()
            }
            attachments.append(attachment)
        

        # Add email metadata to the list
        emails.append({
            'id': message_id.decode(),
            'timestamp': datetime,
            'thread_count': thread_count,
            'from': email_from,
            'to': email_to,
            'subject': subject,
            'attachments': attachments
        })

    # Convert the list of emails to JSON format
    json_data = json.dumps(emails, indent=4)

    # Close the connection to the IMAP server
    imap_server.close()
    imap_server.logout()

    return json_data


@app.route('/download_attachment', methods=['GET'])
def download_attachment():
    message_id = request.args.get('message_id')
    filename = request.args.get('file_name')
    username = request.args.get('username')
    password = request.args.get('password')

    # IMAP settings for Gmail
    imap_host = 'imap.gmail.com'
    imap_port = 993

    # Connect to the Gmail server using IMAP
    imap_server = imaplib.IMAP4_SSL(imap_host, imap_port)
    imap_server.login(username, password)
    imap_server.select('inbox')

    # Fetch the email with the given message ID
    _, msg = imap_server.fetch(message_id, '(RFC822)')
    email_message = email.message_from_bytes(msg[0][1])

    # Find the attachment with the given filename
    attachment_part = None
    if email_message.is_multipart():
        for part in email_message.walk():
            if part.get_filename() == filename:
                attachment_part = part
                break

    if attachment_part:
        # Extract the attachment data and return as a response
        attachment = attachment_part.get_payload(decode=True)
        response = make_response(attachment)
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.headers['Content-Type'] = 'application/pdf'
        return response
    else:
        return make_response(('Attachment not found', 404))


if __name__ == '__main__':
    app.run(port=5000)



