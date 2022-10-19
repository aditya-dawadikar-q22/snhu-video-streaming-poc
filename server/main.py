import base64
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi import Response
from fastapi.templating import Jinja2Templates
from fastapi import Header
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
import datetime
import urllib
import base64
import hmac
import hashlib
import time


from Controller import get_stream_bytes,get_signed_url_for_blob,get_signed_cdn_url


app = FastAPI()

origins = [
    "*",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")
CHUNK_SIZE = 1024*1024*10
video_path = Path("video.mp4")

@app.get('/stream-from-local')
async def getLocalVideoStream(range: str = Header(None)):
    '''
        Video file is present on local machine, and served from a static location using jinja templating.
        The file is read in chunks and sent to the client as chunks with status code 206 (partial content).
        From html5 video tag, the range header is passed automatically, and only that part is streamed.
        range header is required.

        Ref: https://fastapi.tiangolo.com/advanced/custom-response/#fileresponse
    '''
    start, end = range.replace("bytes=", "").split("-")
    start = int(start)
    end = int(end) if end else start + CHUNK_SIZE
    with open(video_path, "rb") as video:
        video.seek(start)
        data = video.read(end - start)
        filesize = str(video_path.stat().st_size)
        headers = {
            'Content-Range': f'bytes {str(start)}-{str(end)}/{filesize}',
            'Accept-Ranges': 'bytes'
        }
        return Response(data, status_code=206, headers=headers, media_type="video/mp4")

@app.get('/stream-from-bucket')
async def getRemoteVideoStream():
    '''
        Video is present on some bucket on cloud, it is fetched using get_bytes function.
        The bytes are sent back to the client as it is with media_type video/mp4.
        Caching should be implemented for fast retrieval. 
        range param is required to allow seek forward/backward.
        response is sent back only when the file is fetched 100% from gcs.
        file cannot be downloaded on UI as bytes stream is sent instead of file. 
        The url can be played directly in a browser and file can be downloded, hence risk of theft.
    '''
    bytes,filesize = get_stream_bytes()
    return Response(bytes, media_type="video/mp4")

@app.get('/stream-from-bucket-with-chunk-size')
async def getRemoteVideoStreamWithChunkSize(range: str = Header(None)):
    '''
        Video is present on some bucket on cloud, it is fetched using get_bytes function with start and end index.
        The bytes are sent back to the client as it is with media_type video/mp4.
        The chunk size should be adjusted, otherwise it will give a bad user exp because of buffering.
        Cache can be implemented for fast retrival.
        range header is required.

        ref: https://developer.mozilla.org/en-US/docs/Web/HTTP/Range_requests#:~:text=We%20can%20request%20a%20single,requesting%20the%20first%201024%20bytes.
    '''
    start, end = range.replace("bytes=", "").split("-")
    start = int(start)
    end = start+CHUNK_SIZE

    bytes,filesize = get_stream_bytes(start,end)

    if end>filesize:
        end = filesize

    chunk = bytes

    headers = {
            'Content-Range': f'bytes {str(start)}-{str(end)}/{filesize}',
            'Accept-Ranges': 'bytes'
        }
    return Response(chunk,headers=headers, status_code=206,media_type="video/mp4")

@app.get('/stream-from-signed-url')
async def getVideoSignedUrl():
    '''
        Returns Signed Url for a video file with a validity period. ideally long enough to run entire video.
        No issues with seek forward and backwards.
        The url can be played directly in a browser and file can be downloded, hence risk of theft.

        Ref: Quota limits for signed URL
        https://stackoverflow.com/questions/65169199/google-cloud-storage-signed-urls-is-there-an-upper-limit-on-the-number-of-is
    '''
    signed_url = get_signed_url_for_blob(filename="abs_path_test_1/index.html")
    return {"content_url":signed_url}

# TODO: Stream from bucket as backend for cloud cdn signed URL
#  ref: https://stackoverflow.com/questions/61409735/how-can-i-implement-a-cdn-with-firebase-storage
#  ref: https://cloud.google.com/cdn/docs/setting-up-cdn-with-bucket

@app.get("/get-cdn-signed-url")
async def getVideoCDNSignedURL():
    '''
        Returns a signed url for cdn content
    '''

    dt = datetime.datetime.now(datetime.timezone.utc)

    expiration_time = dt.replace(tzinfo=None)  + datetime.timedelta(minutes=5)

    # base64_key = "8w0qVya6WWCpQ2-lnLaB3A=="
    # base64_key = "OHcwcVZ5YTZXV0NwUTItbG5MYUIzQT09"
    base64_key = "OHcwcVZ5YTZXV0NwUTItbG5MYUIzQT09Cg=="
    key_name="cdn-key"
    url="http://34.160.224.75/cdn-test-snhu/video.mp4"

    signed_url = get_signed_cdn_url(url=url, 
                                    key_name=key_name, 
                                    base64_key=base64_key, 
                                    expiration_time=expiration_time)
    return {"content_url":signed_url}

@app.get("/get-video-signed-url-for-cdn")
async def getSignedURLForCDN():

    def getBase64String(key):
        sample_string = key
        sample_string_bytes = sample_string.encode("ascii")
        
        base64_bytes = base64.b64encode(sample_string_bytes)
        base64_string = base64_bytes.decode("ascii")
        return base64_string

    url = "http://34.160.224.75/img1.jpeg"

    # key = "8w0qVya6WWCpQ2-lnLaB3A=="
    # key_name = "cdn-key"
    key = "pUJZuM5bHmLaYT9QH23n5g=="
    key_name = "cdn-key-2"
    base64_key = getBase64String(key)

    stripped_url = url.strip()
    parsed_url = urllib.parse.urlsplit(stripped_url)
    query_params = urllib.parse.parse_qs(
        parsed_url.query, keep_blank_values=True)

    epoch = datetime.datetime.utcfromtimestamp(0)
    
    dt = datetime.datetime.now(datetime.timezone.utc)

    expiration_time = dt.replace(tzinfo=None)  + datetime.timedelta(minutes=5)

    expiration_timestamp = int((expiration_time - epoch).total_seconds())
    # expiration_timestamp = int(time.time())+int(datetime.timedelta(seconds=120).total_seconds())
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

    return signed_url


# http://34.160.224.75/img1.jpeg?Expires=1664887409&KeyName=cdn-key-2&Signature=WcJmahFIWI1vFfdV8cnbBi8wPU8=
# http://34.160.224.75/img1.jpeg?Expires=1664886887&KeyName=cdn-key-2&Signature=ndr1oyiFgmhCskdqkPb7KFGTeRc=
# http://34.160.224.75/img1.jpeg?Expires=1664887409&KeyName=cdn-key-2&Signature=wXVAs4KUKXwouH7mso1-8AtvvG8=

# gs://cdn-test-snhu/NS_HUM102_C1_S2_Academic Programs of the Humanities_SCORM1.2/story.html