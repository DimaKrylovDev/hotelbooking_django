from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from .forms import (
    AvailabilitySearchForm,
    BookingCreateForm,
    PasswordChangeForm,
    UserLoginForm,
    UserProfileForm,
    UserRegistrationForm,
    RoomCreateForm,
    RoomUpdateForm,
    BookingUpdateForm,
    ReviewForm,
    ReviewReplyForm,
    ReviewModerationForm
)
from .models import Booking, Room, User, BookingStatus, BookingHistory, Review, RoomType, RoomImage, UserRole, ReviewStatus
from django.views.generic import CreateView, TemplateView, DetailView, DeleteView, ListView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.urls import reverse_lazy
from django.db import IntegrityError
from django.db.models import Q, Count, Sum, Avg
from datetime import timedelta

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_admin

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        return render(
            self.request,
            'main/access_denied.html',
            {
                'title': 'Доступ запрещён',
                'required_role': 'Администратор',
                'message': 'Эта страница доступна только администраторам системы.',
            }
        )

class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.is_staff

    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        return render(
            self.request,
            'main/access_denied.html',
            {
                'title': 'Доступ запрещён',
                'required_role': 'Сотрудник или Администратор',
                'message': 'Эта страница доступна только сотрудникам и администраторам.',
            }
        )

class UserRequiredMixin(UserPassesTestMixin):
    """Миксин для проверки что пользователь авторизован и не является администратором"""
    def test_func(self):
        return self.request.user.is_authenticated and not self.request.user.is_admin and not self.request.user.is_staff and not self.request.user.is_superuser
    
    def handle_no_permission(self):
        if not self.request.user.is_authenticated:
            return redirect('login')
        return render(
            self.request,
            'main/access_denied.html',
            {
                'title': 'Доступ запрещён',
                'required_role': 'Пользователь',
                'message': 'Эта страница доступна только пользователям.',
            }
        )

class HomeView(TemplateView):
    template_name = 'main/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': 'Главная', 
            'today': timezone.localdate(),
        })
        
        search_form = AvailabilitySearchForm(self.request.GET or None)
        context.update({
            'search_form': search_form,
        })
        return context

class SearchResultsView(TemplateView):
    template_name = 'main/search_results.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        rooms = Room.objects.none()
        no_results_message = ''
        search_form = AvailabilitySearchForm(self.request.GET or None)
        nights = 1
        rooms_list = []
        selected_filters = {
            'room_type': self.request.GET.get('room_type') or '',
            'price_min': self.request.GET.get('price_min') or '',
            'price_max': self.request.GET.get('price_max') or '',
            'amenity_wifi': self.request.GET.get('amenity_wifi') is not None,
            'amenity_parking': self.request.GET.get('amenity_parking') is not None,
        }

        if search_form.is_valid():
            destination = search_form.cleaned_data['destination']
            check_in = search_form.cleaned_data['check_in']
            check_out = search_form.cleaned_data['check_out']
            guests = search_form.cleaned_data['guests']

            rooms = (
                Room.objects.get_available_rooms(destination, check_in, check_out)
                .filter(capacity__gte=guests)
                .prefetch_related('images')
            )

            # Фильтры панели
            if selected_filters['room_type']:
                rooms = rooms.filter(room_type=selected_filters['room_type'])

            if selected_filters['price_min']:
                try:
                    rooms = rooms.filter(price_per_night__gte=float(selected_filters['price_min']))
                except ValueError:
                    pass

            if selected_filters['price_max']:
                try:
                    rooms = rooms.filter(price_per_night__lte=float(selected_filters['price_max']))
                except ValueError:
                    pass

            if selected_filters['amenity_wifi']:
                rooms = rooms.filter(
                    Q(amenities__icontains='wi-fi') |
                    Q(amenities__icontains='wifi') |
                    Q(amenities__icontains='вайф')
                )

            if selected_filters['amenity_parking']:
                rooms = rooms.filter(
                    Q(amenities__icontains='парков') |
                    Q(amenities__icontains='parking')
                )

            if not rooms.exists():
                no_results_message = (
                    f"Нет доступных номеров в городе «{destination}» "
                    f"на выбранные даты для {guests} гост(ей)."
                )
            if check_in and check_out and check_out > check_in:
                nights = (check_out - check_in).days

            rooms_list = list(rooms)
            for room in rooms_list:
                room.total_price_for_dates = round(room.price_per_night * nights, 2)

            context.update({
                'destination': destination,
                'check_in': check_in,
                'check_out': check_out,
                'guests': guests,
                'nights': nights,
            })

        if not rooms_list:
            rooms_list = list(rooms)

        context.update({
            'title': 'Результаты поиска',
            'today': timezone.localdate(),
            'search_form': search_form,
            'rooms': rooms_list,
            'search_performed': True,
            'no_results_message': no_results_message,
            'nights': nights,
            'room_types': RoomType.choices,
            'selected_filters': selected_filters,
        })
        return context

def signup_view(request):
    redirect_to = request.GET.get('next') or request.POST.get('next') or 'profile'
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(redirect_to)
    else:
        form = UserRegistrationForm()
    return render(request, 'main/signup.html', {'form': form, 'title': 'Регистрация', 'next': redirect_to})

def login_view(request):
    redirect_to = request.GET.get('next') or request.POST.get('next') or 'profile'
    if request.method == 'POST':
        form = UserLoginForm(request.POST)
        if form.is_valid():
            user = authenticate(request, username=form.cleaned_data['email'], password=form.cleaned_data['password'])
            if user is not None:
                login(request, user)
                return redirect(redirect_to)
            else:
                form.add_error(None, 'Invalid email or password')
    else:
        form = UserLoginForm()
    return render(request, 'main/login.html', {'form': form, 'title': 'Вход', 'next': redirect_to})


class ProfileView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'main/profile.html'
    context_object_name = 'user'

    def get_object(self):
        return self.request.user

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        booking = (
            Booking.objects.filter(guest=self.request.user)
            .exclude(status=BookingStatus.CANCELLED)
            .select_related('room')
            .first()
        )

        user_rooms = (
            Room.objects.filter(room_owner=self.request.user)
            .order_by('-created_at')
        )

        # Бронирования комнат владельца (только активные)
        owner_bookings = (
            Booking.objects.filter(room__room_owner=self.request.user)
            .exclude(status=BookingStatus.CANCELLED)
            .select_related('room', 'guest')
            .order_by('-created_at')
        )

        context.update({
            'title': 'Профиль',
            'booking': booking,
            'user_rooms': user_rooms,
            'owner_bookings': owner_bookings,
        })
        return context

@login_required
def edit_profile_view(request):
    user = request.user
    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileForm(request.POST, instance=user)
            password_form = PasswordChangeForm(user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Профиль успешно обновлён.')
                return redirect('profile')
        elif 'change_password' in request.POST:
            profile_form = UserProfileForm(instance=user)
            password_form = PasswordChangeForm(user, request.POST)
            if password_form.is_valid():
                user.set_password(password_form.cleaned_data['new_password'])
                user.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Пароль успешно изменён.')
                return redirect('profile')
        else:
            profile_form = UserProfileForm(instance=user)
            password_form = PasswordChangeForm(user)
    else:
        profile_form = UserProfileForm(instance=user)
        password_form = PasswordChangeForm(user)

    return render(
        request,
        'main/edit_profile.html',
        {
            'title': 'Редактирование профиля',
            'form': profile_form,
            'password_form': password_form,
        },
    )

@login_required
def logout_view(request):
    if request.method == "POST": 
        logout(request)
        return redirect('home')
    return render(request, 'main/logout.html')

    
MAX_GALLERY_PHOTOS = 5

class RoomCreateView(UserRequiredMixin, CreateView):
    model = Room
    form_class = RoomCreateForm
    template_name = 'main/room_form.html'
    success_url = reverse_lazy('profile')

    def form_valid(self, form):
        form.instance.room_owner = self.request.user
        form.instance.amenities = form.cleaned_data.get('amenities', '')
        response = super().form_valid(form)
        self._save_gallery_images(self.object)
        messages.success(self.request, 'Комната успешно создана!')
        return response

    def _save_gallery_images(self, room):
        gallery_files = self.request.FILES.getlist('gallery_images')
        has_main = bool(room.room_photo)
        slots_available = MAX_GALLERY_PHOTOS - (1 if has_main else 0)
        for image_file in gallery_files[:slots_available]:
            RoomImage.objects.create(room=room, image=image_file)

class RoomDeleteView(UserRequiredMixin, DeleteView):
    model = Room
    template_name = 'main/room_delete.html'
    success_url = reverse_lazy('profile')

    def get_queryset(self):
        return super().get_queryset().filter(room_owner=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Комната удалена.')
        return super().delete(request, *args, **kwargs)


@login_required
def update_room_view(request, pk):
    room = get_object_or_404(Room, pk=pk, room_owner=request.user)

    if request.method == 'POST':
        form = RoomUpdateForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            room = form.save(commit=False)
            room.amenities = form.cleaned_data.get('amenities', '')
            room.save()
            
            gallery_files = request.FILES.getlist('gallery_images')
            existing_count = room.images.count()
            has_main = bool(room.room_photo)
            total_existing = existing_count + (1 if has_main else 0)
            slots_available = max(0, MAX_GALLERY_PHOTOS - total_existing)
            
            for image_file in gallery_files[:slots_available]:
                RoomImage.objects.create(room=room, image=image_file)
            
            messages.success(request, 'Комната успешно обновлена!')
            return redirect('profile')
    else:
        form = RoomUpdateForm(instance=room)

    return render(
        request,
        'main/update_room.html',
        {
            'form': form,
            'title': 'Обновление комнаты',
            'room': room,
        },
    )


class BookingCreateView(UserRequiredMixin, CreateView):
    model = Booking
    form_class = BookingCreateForm
    template_name = 'main/booking_form.html'
    success_url = reverse_lazy('profile')

    def dispatch(self, request, *args, **kwargs):
        self.room = get_object_or_404(Room, pk=self.kwargs['room_id'], is_active=True)
        
        if self.room.room_owner == request.user:
            messages.error(request, 'Вы не можете забронировать свою собственную комнату.')
            return redirect('home')
        
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Бронирование комнаты #{self.room.id}'
        context['room'] = self.room
        context['today'] = timezone.localdate()
        return context

    def form_valid(self, form):
        from .models import BookingStatus
        
        form.instance.guest = self.request.user
        form.instance.room = self.room 
        form.instance.status = BookingStatus.PENDING

        check_in = form.cleaned_data['check_in_date']
        check_out = form.cleaned_data['check_out_date']

        conflicting_bookings = Booking.objects.filter(
            room=self.room,
            check_in_date__lte=check_out,
            check_out_date__gte=check_in,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.PENDING]
        )
        if conflicting_bookings.exists():
            form.add_error(None, 'Эта комната уже забронирована на выбранные даты.')
            return self.form_invalid(form)

        nights = (check_out - check_in).days
        form.instance.total_cost = self.room.price_per_night * nights

        response = super().form_valid(form)

        BookingHistory.objects.create(
            booking=self.object, 
            old_status='',
            new_status=BookingStatus.PENDING,
            changed_by='SYSTEM',
            change_description='Бронирование создано пользователем.'
        )

        messages.success(self.request, 'Бронирование успешно создано!')
        return response

class BookingDeleteView(UserRequiredMixin, DeleteView):
    model = Booking
    template_name = 'main/booking_delete.html'
    success_url = reverse_lazy('profile')

    def get_queryset(self):
        return super().get_queryset().filter(guest=self.request.user)

    def delete(self, request, *args, **kwargs):
        booking = self.get_object()
        old_status = booking.status
        
        # Меняем статус на CANCELLED вместо удаления
        booking.status = BookingStatus.CANCELLED
        booking.save()
        
        # Создаем или обновляем запись в истории
        BookingHistory.objects.update_or_create(
            booking=booking,
            defaults={
                'old_status': old_status,
                'new_status': BookingStatus.CANCELLED,
                'changed_by': request.user.get_full_name() or request.user.email,
                'change_description': 'Бронирование отменено.'
            }
        )
        
        messages.success(request, 'Бронирование отменено.')
        return redirect('profile')
    
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@login_required
def update_booking_view(request, pk):
    from .models import BookingStatus
    
    booking = get_object_or_404(Booking, pk=pk, guest=request.user)

    if request.method == 'POST':
        form = BookingUpdateForm(request.POST, instance=booking)
        if form.is_valid():
            check_in = form.cleaned_data['check_in_date']
            check_out = form.cleaned_data['check_out_date']
            
            # Проверяем доступность комнаты на новые даты (исключая текущее бронирование)
            conflicting_bookings = Booking.objects.filter(
                room=booking.room,
                check_in_date__lte=check_out,
                check_out_date__gte=check_in,
                status__in=[BookingStatus.CONFIRMED, BookingStatus.PENDING]
            ).exclude(pk=booking.pk)
            
            if conflicting_bookings.exists():
                form.add_error(None, 'Эта комната уже забронирована на выбранные даты.')
                return render(
                    request,
                    'main/update_booking.html',
                    {
                        'form': form,
                        'title': 'Обновление брони',
                        'booking': booking,
                        'room': booking.room,
                        'today': timezone.localdate(),
                    },
                )
            
            # Пересчитываем стоимость
            nights = (check_out - check_in).days
            old_cost = booking.total_cost
            booking.total_cost = booking.room.price_per_night * nights
            booking.check_in_date = check_in
            booking.check_out_date = check_out
            booking.save()
            
            # Создаем или обновляем историю
            history, created = BookingHistory.objects.get_or_create(
                booking=booking,
                defaults={
                    'old_status': booking.status,
                    'new_status': booking.status,
                    'changed_by': request.user.get_full_name() or request.user.email,
                    'change_description': f'Даты бронирования изменены. Стоимость: {old_cost:.2f} ₽ → {booking.total_cost:.2f} ₽'
                }
            )
            if not created:
                history.change_description = f'Даты бронирования изменены. Стоимость: {old_cost:.2f} ₽ → {booking.total_cost:.2f} ₽'
                history.changed_by = request.user.get_full_name() or request.user.email
                history.save()
            
            messages.success(request, 'Бронь успешно обновлена!')
            return redirect('profile')
    else:
        form = BookingUpdateForm(instance=booking)

    return render(
        request,
        'main/update_booking.html',
        {
            'form': form,
            'title': 'Обновление брони',
            'booking': booking,
            'room': booking.room,
            'today': timezone.localdate(),
        },
    )


class RoomDetailView(DetailView):
    model = Room
    template_name = 'main/room_detail.html'
    context_object_name = 'room'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
         # Показываем только одобренные отзывы для обычных пользователей
        reviews = Review.objects.filter(
            room=self.object,
            status=ReviewStatus.APPROVED
        ).select_related('guest').order_by('-created_at')
        gallery_images = list(self.object.images.all())
        
        all_photos = []
        if self.object.room_photo:
            all_photos.append(self.object.room_photo.url)
        for img in gallery_images:
            all_photos.append(img.image.url)
        
        extra_photos_count = max(0, len(all_photos) - 5)
        
        booking_for_user = None
        if self.request.user.is_authenticated:
            booking_for_user = (
                Booking.objects.filter(room=self.object, guest=self.request.user)
                .exclude(status=BookingStatus.CANCELLED)
                .first()
            )
        context.update({
            'title': f'Комната #{self.object.id}',
            'reviews': reviews,
            'user_booking_for_room': booking_for_user,
            'all_photos': all_photos,
            'extra_photos_count': extra_photos_count,
        })
        return context

@login_required
def confirm_booking_view(request, pk):
    from .models import BookingStatus
    
    booking = get_object_or_404(Booking, pk=pk)
    
    if booking.guest != request.user and booking.room.room_owner != request.user:
        messages.error(request, 'У вас нет прав для подтверждения этого бронирования.')
        return redirect('profile')
    
    if request.method == 'POST':
        old_status = booking.status
        booking.status = BookingStatus.CONFIRMED
        booking.save()
        
        # Создаем или обновляем историю
        history, created = BookingHistory.objects.get_or_create(
            booking=booking,
            defaults={
                'old_status': old_status,
                'new_status': BookingStatus.CONFIRMED,
                'changed_by': request.user.get_full_name() or request.user.email,
                'change_description': 'Бронирование подтверждено.'
            }
        )
        if not created:
            history.old_status = old_status
            history.new_status = BookingStatus.CONFIRMED
            history.changed_by = request.user.get_full_name() or request.user.email
            history.change_description = 'Бронирование подтверждено.'
            history.save()
        
        messages.success(request, 'Бронирование успешно подтверждено!')
        return redirect('profile')
    
    return render(
        request,
        'main/confirm_booking.html',
        {
            'booking': booking,
            'title': 'Подтверждение бронирования',
        },
    )

@login_required
def booking_history_view(request):
    # Все бронирования пользователя как гостя
    guest_bookings = (
        Booking.objects.filter(guest=request.user)
        .select_related('room', 'review')
        .order_by('-created_at')
    )
    
    # Все бронирования комнат владельца
    owner_bookings = (
        Booking.objects.filter(room__room_owner=request.user)
        .select_related('room', 'guest', 'review')
        .order_by('-created_at')
    )
    
    # Объединяем все бронирования
    all_bookings = list(guest_bookings) + list(owner_bookings)
    # Сортируем по дате создания (новые первыми)
    all_bookings.sort(key=lambda x: x.created_at, reverse=True)
    
    return render(
        request,
        'main/booking_history.html',
        {
            'title': 'История бронирований',
            'bookings': all_bookings,
            'guest_bookings': guest_bookings,
            'owner_bookings': owner_bookings,
        },
    )

class ReviewListView(ListView):
    model = Review
    template_name = 'main/review_list.html'
    context_object_name = 'reviews'
    success_url = reverse_lazy('reviews')

    def get_queryset(self):
        qs = super().get_queryset().select_related('room', 'guest')
        room_id = self.request.GET.get('room')

        if room_id:
            # Для просмотра отзывов к комнате - только одобренные
            qs = qs.filter(room_id=room_id, status=ReviewStatus.APPROVED)
        elif self.request.user.is_authenticated and self.request.user.is_owner:
            # Владелец видит все отзывы к своим комнатам (включая на модерации)
            qs = qs.filter(room__room_owner=self.request.user)
        elif self.request.user.is_authenticated:
            # Пользователь видит свои отзывы в любом статусе
            qs = qs.filter(guest=self.request.user)
        else:
            # Неавторизованные - только одобренные
            qs = qs.filter(status=ReviewStatus.APPROVED)

        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        room_id = self.request.GET.get('room')
        context['title'] = 'Отзывы'
        if room_id:
            context['room_id'] = room_id
        return context

class ReviewCreateView(UserRequiredMixin, CreateView):
    model = Review
    form_class = ReviewForm
    template_name = 'main/review_form.html'
    success_url = reverse_lazy('reviews')

    def dispatch(self, request, *args, **kwargs):
        self.booking = get_object_or_404(Booking, pk=self.kwargs['booking_id'], guest=request.user)
        if self.booking.room.room_owner == request.user:
            messages.error(request, 'У вас нет прав для оставить отзыв для этого бронирования.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Оставить отзыв для бронирования #{self.booking.id}'
        context['booking'] = self.booking
        context['room'] = self.booking.room
        return context

    def form_valid(self, form):
        form.instance.booking = self.booking
        form.instance.room = self.booking.room
        form.instance.guest = self.request.user
        try:
            response = super().form_valid(form)
            messages.success(self.request, 'Отзыв успешно добавлен!')
            return response
        except IntegrityError:
            form.add_error(None, 'Отзыв для этого бронирования уже существует.')
            return self.form_invalid(form)

class ReviewUpdateView(UserRequiredMixin, UpdateView):
    model = Review
    form_class = ReviewForm
    template_name = 'main/review_form.html'
    success_url = reverse_lazy('reviews')

    def get_queryset(self):
        return super().get_queryset().filter(guest=self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, 'Отзыв успешно обновлен.')
        return response

class ReviewDeleteView(UserRequiredMixin, DeleteView):
    model = Review
    template_name = 'main/review_delete.html'
    success_url = reverse_lazy('reviews')

    def get_queryset(self):
        return super().get_queryset().filter(guest=self.request.user)

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, 'Отзыв удален.')
        return super().delete(request, *args, **kwargs)


class ReviewReplyView(LoginRequiredMixin, UpdateView):
    """Ответ владельца на отзыв"""
    model = Review
    form_class = ReviewReplyForm
    template_name = 'main/review_reply.html'
    success_url = reverse_lazy('reviews')

    def get_queryset(self):
        # Только отзывы к комнатам текущего пользователя
        return super().get_queryset().filter(room__room_owner=self.request.user)

    def form_valid(self, form):
        form.instance.owner_reply_at = timezone.now()
        messages.success(self.request, 'Ответ на отзыв успешно добавлен!')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Ответ на отзыв'
        context['review'] = self.object
        return context


class ReviewModerationListView(StaffRequiredMixin, ListView):
    """Список отзывов для модерации (staff/admin)"""
    model = Review
    template_name = 'main/review_moderation_list.html'
    context_object_name = 'reviews'

    def get_queryset(self):
        qs = super().get_queryset().select_related('room', 'guest', 'moderated_by')
        status_filter = self.request.GET.get('status', '')
        
        if status_filter:
            qs = qs.filter(status=status_filter)
        
        return qs.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Модерация отзывов'
        context['review_statuses'] = ReviewStatus.choices
        context['current_status'] = self.request.GET.get('status', '')
        context['pending_count'] = Review.objects.filter(status=ReviewStatus.PENDING).count()
        return context


class ReviewModerateView(StaffRequiredMixin, UpdateView):
    """Модерация конкретного отзыва (staff/admin)"""
    model = Review
    form_class = ReviewModerationForm
    template_name = 'main/review_moderate.html'
    success_url = reverse_lazy('review_moderation_list')

    def form_valid(self, form):
        form.instance.moderated_by = self.request.user
        form.instance.moderated_at = timezone.now()
        status_display = form.instance.get_status_display()
        messages.success(self.request, f'Отзыв #{self.object.id} - статус изменён на "{status_display}"')
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = f'Модерация отзыва #{self.object.id}'
        context['review'] = self.object
        return context


class  ReviewQuickModerateView(StaffRequiredMixin, DetailView):
    """Быстрая модерация отзыва (одобрить/отклонить)"""
    model = Review

    def get(self, request, *args, **kwargs):
        review = self.get_object()
        action = kwargs.get('action')
        
        if action == 'approve':
            review.status = ReviewStatus.APPROVED
            message = 'Отзыв одобрен.'
        elif action == 'reject':
            review.status = ReviewStatus.REJECTED
            message = 'Отзыв отклонён.'
        else:
            messages.error(request, 'Неизвестное действие.')
            return redirect('review_moderation_list')
        
        review.moderated_by = request.user
        review.moderated_at = timezone.now()
        review.save()
        
        messages.success(request, message)
        return redirect('review_moderation_list')

class MyRoomsBookingsView(LoginRequiredMixin, ListView):
    """Просмотр бронирований по комнатам владельца"""
    template_name = 'main/my_rooms_bookings.html'
    context_object_name = 'rooms'

    def get_queryset(self):
        return Room.objects.filter(room_owner=self.request.user).prefetch_related(
            'bookings__guest',
            'images'
        ).order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Бронирования моих комнат'
        
        # Статистика
        total_bookings = Booking.objects.filter(room__room_owner=self.request.user).count()
        active_bookings = Booking.objects.filter(
            room__room_owner=self.request.user,
            status__in=[BookingStatus.PENDING, BookingStatus.CONFIRMED]
        ).count()
        
        context['total_bookings'] = total_bookings
        context['active_bookings'] = active_bookings
        return context