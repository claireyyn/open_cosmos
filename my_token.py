# https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html#python
from oauthlib.oauth2 import BackendApplicationClient
from requests_oauthlib import OAuth2Session


# Your client credentials
client_id = 'sh-5db12232-c4f0-437f-a624-bb8a2ceb2622'
client_secret = 'ntxVcg096P2raTve1x0hN47Z0iHnDhzW'

# Create a session
client = BackendApplicationClient(client_id=client_id)
oauth = OAuth2Session(client=client)

# Get token for the session
token = oauth.fetch_token(token_url='https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token',
                          client_secret=client_secret)

# All requests using this session will have an access token automatically added
# resp = oauth.get("...")
# print(resp.content)



def sentinelhub_compliance_hook(response):
    response.raise_for_status()
    return response

oauth.register_compliance_hook("access_token_response", sentinelhub_compliance_hook)
