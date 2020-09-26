from typing import Optional

from .exceptions import (
    AuthorizationCodeExpiredError,
    InvalidAuthorizationCodeError,
    InvalidClientError,
    InvalidGrantTypeError,
    InvalidRedirectUriError,
    InvalidRefreshTokenError,
    InvalidUsernameOrPasswordError,
    MissingAuthorizationCodeError,
    MissingGrantTypeError,
    MissingPasswordError,
    MissingRedirectUriError,
    MissingRefreshTokenError,
    MissingUsernameError,
    RefreshTokenExpiredError,
)
from .models import Client
from .request_validator import BaseRequestValidator
from .requests import Request
from .responses import TokenResponse
from .types import GrantType, RequestMethod
from .utils import check_basic_auth


class GrantTypeBase(BaseRequestValidator):
    allowed_methods = (RequestMethod.POST,)
    grant_type: Optional[GrantType] = None

    async def create_token_response(self, request: Request) -> TokenResponse:
        client = await self.validate_request(request)
        token = await self.db.create_token(request, client)

        return TokenResponse(
            expires_in=token.expires_in,
            refresh_token_expires_in=token.refresh_token_expires_in,
            access_token=token.access_token,
            refresh_token=token.refresh_token,
            scope=token.scope,
            token_type=token.token_type,
        )

    async def validate_request(self, request: Request) -> Client:
        await super().validate_request(request)

        client_id, client_secret = check_basic_auth(request)

        if not request.post.grant_type:
            raise MissingGrantTypeError()

        if self.grant_type != request.post.grant_type:
            raise InvalidGrantTypeError()

        client = await self.db.get_client(
            request, client_id=client_id, client_secret=client_secret
        )

        if not client:
            raise InvalidClientError()

        if not client.check_grant_type(request.post.grant_type):
            raise InvalidGrantTypeError()

        return client


class AuthorizationCodeGrantType(GrantTypeBase):
    grant_type: GrantType = GrantType.TYPE_AUTHORIZATION_CODE

    async def validate_request(self, request: Request) -> Client:
        client = await super().validate_request(request)

        if not request.post.redirect_uri:
            raise MissingRedirectUriError()

        if not client.check_redirect_uri(request.post.redirect_uri):
            raise InvalidRedirectUriError()

        if not request.post.code:
            raise MissingAuthorizationCodeError()

        authorization_code = await self.db.get_authorization_code(request, client)

        if not authorization_code:
            raise InvalidAuthorizationCodeError()

        if authorization_code.is_expired():
            raise AuthorizationCodeExpiredError()

        await self.db.delete_authorization_code(request, authorization_code)

        return client


class PasswordGrantType(GrantTypeBase):
    grant_type: GrantType = GrantType.TYPE_PASSWORD

    async def validate_request(self, request: Request) -> Client:
        client = await super().validate_request(request)

        if not request.post.password:
            raise MissingPasswordError()

        if not request.post.username:
            raise MissingUsernameError()

        user = await self.db.authenticate(request)

        if not user:
            raise InvalidUsernameOrPasswordError()

        return client


class RefreshTokenGrantType(GrantTypeBase):
    grant_type: GrantType = GrantType.TYPE_REFRESH_TOKEN

    async def validate_request(self, request: Request) -> Client:
        client = await super().validate_request(request)

        if not request.post.refresh_token:
            raise MissingRefreshTokenError()

        token = await self.db.get_refresh_token(request, client)

        if not token:
            raise InvalidRefreshTokenError()

        if token.refresh_token_expired:
            raise RefreshTokenExpiredError()

        await self.db.revoke_token(request, token)

        return client


class ClientCredentialsGrantType(GrantTypeBase):
    grant_type: GrantType = GrantType.TYPE_CLIENT_CREDENTIALS
