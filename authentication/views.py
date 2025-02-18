from urllib.parse import urlencode
from django.forms import ValidationError
from rest_framework import serializers
from rest_framework.views import APIView
from django.conf import settings
from django.shortcuts import redirect
from rest_framework.response import Response
from rest_framework import status
from .mixins import PublicApiMixin, ApiErrorsMixin
from .utils import google_get_access_token, google_get_user_info, generate_tokens_for_user
from .models import User
from .serializers import UserSerializer


class GoogleLoginApi(PublicApiMixin, ApiErrorsMixin, APIView):
    class InputSerializer(serializers.Serializer):
        code = serializers.CharField(required=False)
        error = serializers.CharField(required=False)

    def get(self, request, *args, **kwargs):
        input_serializer = self.InputSerializer(data=request.GET)
        input_serializer.is_valid(raise_exception=True)

        validated_data = input_serializer.validated_data

        code = validated_data.get('code')
        error = validated_data.get('error')

        login_url = f'{settings.BASE_FRONTEND_URL}'

        if error or not code:
            params = urlencode({'error': error})
            return redirect(f'{login_url}?{params}')

        redirect_uri = f'{settings.BASE_FRONTEND_URL}/google'
        
        try:
            access_token = google_get_access_token(code=code, redirect_uri=redirect_uri)
            user_data = google_get_user_info(access_token=access_token)
        except ValidationError as e:
            params = urlencode({'error': str(e)})
            return redirect(f'{login_url}?{params}')
        except Exception as e:
            params = urlencode({'error': 'An error occurred while processing your request.'})
            return redirect(f'{login_url}?{params}')

        email = user_data.get('email')
        first_name = user_data.get('given_name', '')
        last_name = user_data.get('family_name', '')

        # Ensure the username is unique
        base_username = email.split('@')[0]
        username = base_username
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{suffix}"
            suffix += 1

        # Check if the user already exists by email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Create a new user
            user = User.objects.create(
                username=username,
                email=email,
                first_name=first_name,
                last_name=last_name,
                registration_method='google'
            )

        # Generate tokens
        access_token, refresh_token = generate_tokens_for_user(user)

        # Prepare response
        response_data = {
            'user': UserSerializer(user).data,
            'access_token': str(access_token),
            'refresh_token': str(refresh_token)
        }

        return Response(response_data, status=status.HTTP_200_OK)
