import re
from django.shortcuts import redirect, render
from django.urls import reverse


class RoleRequiredMiddleware:    
    PUBLIC_URLS = [
        r'^/$',
        r'^/search/',
        r'^/signup/',
        r'^/login/',
        r'^/room/\d+/$',  
        r'^/reviews/$',   
        r'^/admin/',
        r'^/media/',
        r'^/static/',
    ]
    
    ADMIN_REQUIRED_URLS = [
        r'^/admin/',
    ]
    
    STAFF_REQUIRED_URLS = [
        r'^/moderation/',
    ]
    
    USER_ONLY_URLS = [
        r'^/room/create/',
        r'^/room/\d+/update/',
        r'^/room/\d+/delete/',
        r'^/booking/room/\d+/create/',
        r'^/booking/\d+/update/',
        r'^/booking/\d+/delete/',
        r'^/booking/\d+/review/create/',
        r'^/review/\d+/update/',
        r'^/review/\d+/delete/',
    ]
    
    LOGIN_REQUIRED_URLS = [
        r'^/profile/',
        r'^/logout/',
        r'^/edit_profile/',
        r'^/booking/history/',
        r'^/booking/\d+/confirm/',
        r'^/review/\d+/reply/',
        r'^/my-rooms/bookings/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response
        self.public_patterns = [re.compile(p) for p in self.PUBLIC_URLS]
        self.admin_patterns = [re.compile(p) for p in self.ADMIN_REQUIRED_URLS]
        self.staff_patterns = [re.compile(p) for p in self.STAFF_REQUIRED_URLS]
        self.user_only_patterns = [re.compile(p) for p in self.USER_ONLY_URLS]
        self.login_patterns = [re.compile(p) for p in self.LOGIN_REQUIRED_URLS]

    def __call__(self, request):
        path = request.path
        
        if self._matches_any(path, self.public_patterns):
            return self.get_response(request)
        
        if not request.user.is_authenticated:
            if (self._matches_any(path, self.login_patterns) or
                self._matches_any(path, self.admin_patterns) or
                self._matches_any(path, self.staff_patterns) or
                self._matches_any(path, self.user_only_patterns)):
                return redirect(f"{reverse('login')}?next={path}")
            return self.get_response(request)
        
        if self._matches_any(path, self.admin_patterns):
            if not request.user.is_admin:
                return self._access_denied(
                    request,
                    required_role='Администратор',
                    message='Эта страница доступна только администраторам системы.'
                )
        
        if self._matches_any(path, self.staff_patterns):
            if not request.user.is_staff:
                return self._access_denied(
                    request,
                    required_role='Сотрудник или Администратор',
                    message='Эта страница доступна только сотрудникам и администраторам.'
                )
        
        if self._matches_any(path, self.user_only_patterns):
            if request.user.is_admin or request.user.is_staff or request.user.is_superuser:
                return self._access_denied(
                    request,
                    required_role='Пользователь',
                    message='Эта страница доступна только обычным пользователям.'
                )
        
        return self.get_response(request)

    def _matches_any(self, path, patterns):
        return any(pattern.match(path) for pattern in patterns)

    def _access_denied(self, request, required_role, message):
        return render(
            request,
            'main/access_denied.html',
            {
                'title': 'Доступ запрещён',
                'required_role': required_role,
                'message': message,
            },
            status=403
        )
