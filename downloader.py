"""Experimental extractor for public Snapchat web-page JSON. No login bypass."""
import json
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin
import urllib.request
import urllib.error
from contextlib import contextmanager

PAGE_HOSTS = {'snapchat.com', 'www.snapchat.com', 't.snapchat.com'}
MEDIA_ROOTS = ('snapchat.com', 'sc-cdn.net', 'snap.com', 'snapkit.com')
MAX_BYTES = 45 * 1024 * 1024

class DownloadError(Exception):
    pass

def validate_url(url, media=False):
    p = urlsplit(url)
    host = (p.hostname or '').lower()
    allowed = any(host == root or host.endswith('.' + root) for root in MEDIA_ROOTS) if media else host in PAGE_HOSTS
    if p.scheme != 'https' or not allowed or p.username or p.password or p.port not in (None, 443):
        raise DownloadError('الرابط غير مدعوم. أرسل رابط HTTPS من سناب شات.')
    return url

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args):
        return None

class Response:
    def __init__(self, response):
        self.response = response
        self.headers = response.headers
    def iter_content(self, size):
        while chunk := self.response.read(size):
            yield chunk

@contextmanager
def get(url, media=False):
    opener = urllib.request.build_opener(NoRedirect())
    for _ in range(6):
        validate_url(url, media)
        request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            response = opener.open(request, timeout=30)
        except urllib.error.HTTPError as exc:
            if exc.code not in (301, 302, 303, 307, 308):
                exc.close()
                raise DownloadError('تعذر الوصول إلى الرابط العام.') from None
            location = exc.headers.get('Location')
            exc.close()
            if not location:
                raise DownloadError('تعذر فتح الرابط.')
            url = urljoin(url, location)
            continue
        try:
            yield Response(response)
        finally:
            response.close()
        return
    raise DownloadError('عدد تحويلات الرابط كبير.')

class Scripts(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.documents = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'script' and (a.get('id') == '__NEXT_DATA__' or a.get('type') == 'application/json'):
            self.active = True
            self.parts = []
    def handle_data(self, data):
        if self.active:
            self.parts.append(data)
    def handle_endtag(self, tag):
        if tag == 'script' and self.active:
            try:
                self.documents.append(json.loads(''.join(self.parts)))
            except ValueError:
                pass
            self.active = False

def extract_media(html):
    parser = Scripts()
    parser.feed(html)
    found = []
    def visit(node):
        if isinstance(node, dict):
            for key, value in node.items():
                if key.lower() in ('mediaurl', 'videourl', 'imageurl') and isinstance(value, str):
                    try:
                        validate_url(value, media=True)
                        if value not in found:
                            found.append(value)
                    except (ValueError, DownloadError):
                        pass
                else:
                    visit(value)
        elif isinstance(node, list):
            for child in node:
                visit(child)
    for document in parser.documents:
        visit(document)
    return found

def media_links(url):
    with get(url) as r:
        chunks, size = [], 0
        for chunk in r.iter_content(65536):
            size += len(chunk)
            if size > 8 * 1024 * 1024:
                raise DownloadError('صفحة الرابط أكبر من الحد المسموح.')
            chunks.append(chunk)
    links = extract_media(b''.join(chunks).decode('utf-8', errors='replace'))
    if not links:
        raise DownloadError('لم أجد وسائط عامة في الرابط. قد تكون القصة خاصة أو منتهية، أو يحتاج المستخرج إلى تحديث.')
    return links[:20]

def download(url, directory, index):
    with get(url, media=True) as r:
        mime = r.headers.get('Content-Type', '').split(';')[0].lower()
        extensions = {'video/mp4': '.mp4', 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp'}
        if mime not in extensions:
            raise DownloadError('صيغة الوسائط غير مدعومة أو تتطلب معالجة إضافية.')
        path = directory / (str(index) + extensions[mime])
        size = 0
        with path.open('wb') as f:
            for chunk in r.iter_content(65536):
                size += len(chunk)
                if size > MAX_BYTES:
                    raise DownloadError('حجم هذا المقطع يتجاوز حد البوت: 45 ميجابايت.')
                f.write(chunk)
        if not size:
            raise DownloadError('ملف الوسائط فارغ.')
        return path
