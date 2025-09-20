import hashlib
import hmac
import json
import base64
from fastapi import HTTPException
from sqlmodel import Session
from sqlmodel.sql.expression import select


SIGNING_SECRET = "12345"


def comprehensive_signature_debug(signature: str, body: bytes):
    """
    Comprehensive debugging to figure out ScoreApp's signature method
    """
    print("=== COMPREHENSIVE SIGNATURE DEBUG ===")
    print(f"Received signature: {signature}")
    print(f"Body length: {len(body)} bytes")
    
    # Print raw body in different formats for analysis
    body_str = body.decode('utf-8')
    print(f"Body as string: {body_str}")
    print(f"Body hex: {body.hex()}")
    
    # Test different secret key possibilities
    possible_secrets = [
        "12345",
        '"12345"',
        "'12345'",
        "12345 ",  # with trailing space
        " 12345",  # with leading space
        "Your webhook secret key",
        "",
        "test",
        "webhook",
        "scoreapp",
        "secret",
        # Maybe it's base64 encoded?
        base64.b64encode(b"12345").decode(),
    ]
    
    print("\n=== TESTING DIFFERENT SECRET KEYS ===")
    for secret in possible_secrets:
        try:
            # Test raw body
            sig_raw = hmac.new(secret.encode('utf-8'), body, hashlib.sha256).hexdigest()
            match_raw = hmac.compare_digest(signature, sig_raw)
            
            # Test with parsed JSON (compact)
            try:
                parsed = json.loads(body_str)
                compact_json = json.dumps(parsed, separators=(',', ':'))
                sig_compact = hmac.new(secret.encode('utf-8'), compact_json.encode('utf-8'), hashlib.sha256).hexdigest()
                match_compact = hmac.compare_digest(signature, sig_compact)
            except:
                sig_compact = "JSON_ERROR"
                match_compact = False
            
            # Test with parsed JSON (spaced)
            try:
                parsed = json.loads(body_str)
                spaced_json = json.dumps(parsed)
                sig_spaced = hmac.new(secret.encode('utf-8'), spaced_json.encode('utf-8'), hashlib.sha256).hexdigest()
                match_spaced = hmac.compare_digest(signature, sig_spaced)
            except:
                sig_spaced = "JSON_ERROR"
                match_spaced = False
            
            # Print results
            status_raw = "✅ MATCH!" if match_raw else "❌"
            status_compact = "✅ MATCH!" if match_compact else "❌"
            status_spaced = "✅ MATCH!" if match_spaced else "❌"
            
            print(f"Secret: '{secret}'")
            print(f"  Raw body: {sig_raw[:16]}... {status_raw}")
            print(f"  Compact JSON: {sig_compact[:16]}... {status_compact}")
            print(f"  Spaced JSON: {sig_spaced[:16]}... {status_spaced}")
            
            if match_raw or match_compact or match_spaced:
                print(f"🎉 FOUND MATCHING SECRET: '{secret}'")
                return True, secret
                
        except Exception as e:
            print(f"Secret '{secret}' caused error: {e}")
    
    print("\n=== TRYING DIFFERENT HASH ALGORITHMS ===")
    # Maybe they're not using SHA256?
    hash_algorithms = [
        ('md5', hashlib.md5),
        ('sha1', hashlib.sha1),
        ('sha224', hashlib.sha224),
        ('sha256', hashlib.sha256),
        ('sha384', hashlib.sha384),
        ('sha512', hashlib.sha512),
    ]
    
    test_secret = "12345"
    for name, hash_func in hash_algorithms:
        try:
            sig = hmac.new(test_secret.encode(), body, hash_func).hexdigest()
            match = hmac.compare_digest(signature, sig)
            status = "✅ MATCH!" if match else "❌"
            print(f"{name.upper()}: {sig[:16]}... {status}")
            
            if match:
                print(f"🎉 FOUND MATCHING ALGORITHM: {name.upper()}")
                return True, f"{name.upper()} with secret '{test_secret}'"
        except Exception as e:
            print(f"{name.upper()}: Error - {e}")
    
    print("\n=== TRYING DIFFERENT ENCODINGS ===")
    encodings = ['utf-8', 'ascii', 'latin-1', 'utf-16', 'utf-32']
    for encoding in encodings:
        try:
            encoded_body = body_str.encode(encoding)
            sig = hmac.new(test_secret.encode(), encoded_body, hashlib.sha256).hexdigest()
            match = hmac.compare_digest(signature, sig)
            status = "✅ MATCH!" if match else "❌"
            print(f"Encoding {encoding}: {sig[:16]}... {status}")
            
            if match:
                print(f"🎉 FOUND MATCHING ENCODING: {encoding}")
                return True, f"Encoding: {encoding}"
        except Exception as e:
            print(f"Encoding {encoding}: Error - {e}")
    
    print("=== END COMPREHENSIVE DEBUG ===\n")
    return False, None



async def create_score_card_result():
    """
    Create score card result in DB
    """
    pass


async def create_or_update_score_card_result():
    """
    Create or update a score card result
    """
    pass

# def create_new_account_in_db(account_organisation: str, session: Session):
#     """
#     Save New Account to DB
#     """
#     account_unique_id = token_hex(8)
#     account = Account(account_organisation=account_organisation,
#                       account_unique_id=account_unique_id)
#     session.add(account)
#     session.commit()
#     session.refresh(account)
    
#     return account