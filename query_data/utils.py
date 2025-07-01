from urllib.parse import urlparse

def normalize_origin(origin: str) -> str:
    """
    Normalizes an origin URL for consistent comparison.

    - Strips protocol (http://, https://).
    - Strips 'www.' subdomain.
    - Handles cases where no protocol is given.
    - Returns the cleaned hostname.

    Examples:
        'https://www.mydomain.com' -> 'mydomain.com'
        'https://mydomain.com'     -> 'mydomain.com'
        'http://mydomain.com'      -> 'mydomain.com'
        'mydomain.com'             -> 'mydomain.com'
    """
    if not origin or not isinstance(origin, str):
        return ""

    # urlparse works best if a scheme is present.
    # If not, we add a dummy one to parse the netloc correctly.
    if not origin.startswith(('http://', 'https://')):
        parsed = urlparse(f"//{origin.strip()}", scheme="https")
    else:
        parsed = urlparse(origin.strip())
    
    hostname = parsed.hostname
    
    if not hostname:
        return ""

    # Remove 'www.' prefix if it exists
    if hostname.startswith("www."):
        hostname = hostname[4:]
        
    return hostname.lower()