import firebase_admin
from firebase_admin import storage
import datetime
import urllib
import base64
import hmac
import hashlib

cred_obj = firebase_admin.credentials.Certificate('/home/aditya/Desktop/SNHU/oppi-glidepath-dev-proj-4086-d3c6708c8ce4.json')
default_app = firebase_admin.initialize_app(cred_obj)

# contentServingBucket = storage.bucket("content-serving-bucket")
contentServingBucket = storage.bucket("cdn-test-snhu")

def get_stream_bytes(start=None,end=None):

    # GET blob as bytes
    video_blob = contentServingBucket.get_blob("pexels-cottonbro-7170782.mp4") 
    video_bytes = video_blob.download_as_bytes(start=start,end=end)
    return video_bytes,video_blob.size

def get_signed_url_for_blob(filename):

    # video_blob = contentServingBucket.get_blob("pexels-cottonbro-7170782.mp4") 
    video_blob = contentServingBucket.get_blob(filename) 

    url = video_blob.generate_signed_url(
        version="v4",
        # This URL is valid for 15 minutes
        expiration=datetime.timedelta(minutes=10),
        # Allow GET requests using this URL.
        method="GET",
    )

    return url

def get_signed_cdn_url(url, key_name, base64_key, expiration_time):
    """Gets the Signed URL string for the specified URL and configuration.

    Args:
        url: URL to sign as a string.
        key_name: name of the signing key as a string.
        base64_key: signing key as a base64 encoded string.
        expiration_time: expiration time as a UTC datetime object.

    Returns:
        Returns the Signed URL appended with the query parameters based on the
        specified configuration.
    """
    stripped_url = url.strip()
    parsed_url = urllib.parse.urlsplit(stripped_url)
    query_params = urllib.parse.parse_qs(
        parsed_url.query, keep_blank_values=True)
    epoch = datetime.datetime.utcfromtimestamp(0)
    expiration_timestamp = int((expiration_time - epoch).total_seconds())
    decoded_key = base64.urlsafe_b64decode(base64_key)

    url_pattern = u'{url}{separator}Expires={expires}&KeyName={key_name}'

    url_to_sign = url_pattern.format(
            url=stripped_url,
            separator='&' if query_params else '?',
            expires=expiration_timestamp,
            key_name=key_name)

    digest = hmac.new(
        decoded_key, url_to_sign.encode('utf-8'), hashlib.sha1).digest()
    signature = base64.urlsafe_b64encode(digest).decode('utf-8')

    signed_url = u'{url}&Signature={signature}'.format(
            url=url_to_sign, signature=signature)

    # print(signed_url)
    return signed_url