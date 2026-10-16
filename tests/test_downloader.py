import unittest
from downloader import validate_url, extract_media, DownloadError

class Tests(unittest.TestCase):
    def test_valid(self):
        self.assertEqual(validate_url('https://www.snapchat.com/add/user'), 'https://www.snapchat.com/add/user')
    def test_short_link_and_official_subdomains(self):
        for url in ['https://snapchat.com/t/sr8N07sW', 'https://story.snapchat.com/example', 'https://web.snapchat.com/example']:
            with self.subTest(url=url):
                self.assertEqual(validate_url(url), url)

    def test_media_error_names_host(self):
        with self.assertRaisesRegex(DownloadError, 'example.org'):
            validate_url('https://example.org/video.mp4', media=True)

    def test_reject_untrusted_urls(self):
        for url in ['http://www.snapchat.com/x', 'https://snapchat.com.evil.com/x', 'https://localhost/x', 'https://user@www.snapchat.com/x', 'https://www.snapchat.com:8080/x']:
            with self.subTest(url=url), self.assertRaises(DownloadError):
                validate_url(url)
    def test_extract_dedup_and_filter(self):
        page = '<script id="__NEXT_DATA__">{"props":{"snaps":[{"mediaUrl":"https://cf-st.sc-cdn.net/a.mp4"},{"mediaUrl":"https://cf-st.sc-cdn.net/a.mp4"},{"imageUrl":"https://evil.com/a.jpg"}]}}</script>'
        self.assertEqual(extract_media(page), ['https://cf-st.sc-cdn.net/a.mp4'])
    def test_unavailable(self):
        self.assertEqual(extract_media('<html>Login required</html>'), [])
    def test_invalid_json(self):
        self.assertEqual(extract_media('<script id="__NEXT_DATA__">invalid</script>'), [])

if __name__ == '__main__':
    unittest.main()
