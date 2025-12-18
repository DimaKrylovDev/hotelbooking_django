from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.db.models import Count, Sum, Avg
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import User, Room, RoomImage, Booking, Review, BookingHistory, UserRole, BookingStatus, ReviewStatus


# Настройка заголовков админки
admin.site.site_header = "🏨 Hotel Booking - Админ-панель"
admin.site.site_title = "Hotel Booking Admin"
admin.site.index_title = "Управление системой бронирования"


# ==================== USER ====================
@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ('id', 'email', 'full_name', 'phone', 'role_badge', 'is_active_badge', 'rooms_count', 'bookings_count', 'created_at')
    list_filter = ('role', 'is_active', 'is_superuser', 'created_at')
    search_fields = ('email', 'first_name', 'last_name', 'phone')
    ordering = ('-created_at',)
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('email', 'password')
        }),
        ('Персональные данные', {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        ('Права доступа', {
            'fields': ('role', 'is_active', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ('collapse',)
        }),
        ('Даты', {
            'fields': ('last_login',),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Создание пользователя', {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'phone', 'password1', 'password2', 'role'),
        }),
    )
    
    readonly_fields = ('last_login', 'created_at')
    
    def full_name(self, obj):
        return obj.get_full_name()
    full_name.short_description = 'Имя'
    
    def role_badge(self, obj):
        colors = {
            'user': '#0066ff',
            'staff': '#ff9800',
            'admin': '#9c27b0',
        }
        color = colors.get(obj.role, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, obj.get_role_display()
        )
    role_badge.short_description = 'Роль'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28a745;">● Активен</span>')
        return format_html('<span style="color: #dc3545;">● Заблокирован</span>')
    is_active_badge.short_description = 'Статус'
    
    def rooms_count(self, obj):
        count = obj.rooms.count()
        if count > 0:
            return format_html('<a href="{}?room_owner__id={}">{} комнат</a>',
                reverse('admin:main_room_changelist'), obj.id, count)
        return '0'
    rooms_count.short_description = 'Комнат'
    
    def bookings_count(self, obj):
        count = obj.bookings.count()
        if count > 0:
            return format_html('<a href="{}?guest__id={}">{} бронирований</a>',
                reverse('admin:main_booking_changelist'), obj.id, count)
        return '0'
    bookings_count.short_description = 'Бронирований'
    
    actions = ['make_staff', 'make_admin', 'make_user', 'activate_users', 'deactivate_users']
    
    @admin.action(description='Сделать сотрудником')
    def make_staff(self, request, queryset):
        queryset.update(role=UserRole.STAFF)
        self.message_user(request, f'{queryset.count()} пользователей стали сотрудниками')
    
    @admin.action(description='Сделать администратором')
    def make_admin(self, request, queryset):
        queryset.update(role=UserRole.ADMIN)
        self.message_user(request, f'{queryset.count()} пользователей стали администраторами')
    
    @admin.action(description='Сделать обычным пользователем')
    def make_user(self, request, queryset):
        queryset.update(role=UserRole.USER)
        self.message_user(request, f'{queryset.count()} пользователей стали обычными')
    
    @admin.action(description='Активировать пользователей')
    def activate_users(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} пользователей активированы')
    
    @admin.action(description='Заблокировать пользователей')
    def deactivate_users(self, request, queryset):
        queryset.exclude(id=request.user.id).update(is_active=False)
        self.message_user(request, f'Пользователи заблокированы (кроме вас)')


# ==================== ROOM ====================
class RoomImageInline(admin.TabularInline):
    model = RoomImage
    extra = 1
    max_num = 5


@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_type_badge', 'address', 'owner_link', 'price_display', 'capacity', 'is_active_badge', 'bookings_count', 'avg_rating', 'created_at')
    list_filter = ('room_type', 'is_active', 'address', 'created_at')
    search_fields = ('address', 'room_owner__email', 'room_owner__first_name')
    ordering = ('-created_at',)
    list_per_page = 25
    inlines = [RoomImageInline]
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('room_owner', 'room_type', 'address', 'price_per_night')
        }),
        ('Характеристики', {
            'fields': ('capacity', 'size', 'amenities')
        }),
        ('Медиа', {
            'fields': ('room_photo',)
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
    )
    
    def room_type_badge(self, obj):
        colors = {
            'Standard': '#6c757d',
            'Deluxe': '#0066ff',
            'Suite': '#9c27b0',
        }
        color = colors.get(obj.room_type, '#666')
        return format_html(
            '<span style="background: {}; color: white; padding: 3px 10px; border-radius: 12px; font-size: 11px;">{}</span>',
            color, obj.get_room_type_display()
        )
    room_type_badge.short_description = 'Тип'
    
    def owner_link(self, obj):
        return format_html('<a href="{}">{}</a>',
            reverse('admin:main_user_change', args=[obj.room_owner.id]),
            obj.room_owner.get_full_name())
    owner_link.short_description = 'Владелец'
    
    def price_display(self, obj):
        return format_html('<strong>{} ₽</strong>/ночь', int(obj.price_per_night))
    price_display.short_description = 'Цена'
    
    def is_active_badge(self, obj):
        if obj.is_active:
            return format_html('<span style="color: #28a745;">● Активна</span>')
        return format_html('<span style="color: #dc3545;">● Неактивна</span>')
    is_active_badge.short_description = 'Статус'
    
    def bookings_count(self, obj):
        count = obj.bookings.count()
        if count > 0:
            return format_html('<a href="{}?room__id={}">{}</a>',
                reverse('admin:main_booking_changelist'), obj.id, count)
        return '0'
    bookings_count.short_description = 'Бронирований'
    
    def avg_rating(self, obj):
        reviews = Review.objects.filter(room=obj, status=ReviewStatus.APPROVED)
        if reviews.exists():
            avg = reviews.aggregate(avg=Avg('rating'))['avg']
            return format_html('<span style="color: #f59e0b;">⭐ {:.1f}</span>', avg)
        return '—'
    avg_rating.short_description = 'Рейтинг'
    
    actions = ['activate_rooms', 'deactivate_rooms']
    
    @admin.action(description='Активировать комнаты')
    def activate_rooms(self, request, queryset):
        queryset.update(is_active=True)
        self.message_user(request, f'{queryset.count()} комнат активированы')
    
    @admin.action(description='Деактивировать комнаты')
    def deactivate_rooms(self, request, queryset):
        queryset.update(is_active=False)
        self.message_user(request, f'{queryset.count()} комнат деактивированы')


# ==================== BOOKING ====================
@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest_link', 'room_link', 'dates_display', 'total_cost_display', 'status_badge', 'created_at')
    list_filter = ('status', 'created_at', 'check_in_date')
    search_fields = ('guest__email', 'guest__first_name', 'room__address')
    ordering = ('-created_at',)
    list_per_page = 25
    date_hierarchy = 'check_in_date'
    
    fieldsets = (
        ('Участники', {
            'fields': ('guest', 'room')
        }),
        ('Даты', {
            'fields': ('check_in_date', 'check_out_date')
        }),
        ('Финансы и статус', {
            'fields': ('total_cost', 'status')
        }),
    )
    
    def guest_link(self, obj):
        return format_html('<a href="{}">{}</a><br><small style="color:#666;">{}</small>',
            reverse('admin:main_user_change', args=[obj.guest.id]),
            obj.guest.get_full_name(),
            obj.guest.email)
    guest_link.short_description = 'Гость'
    
    def room_link(self, obj):
        return format_html('<a href="{}">{}</a><br><small style="color:#666;">{}</small>',
            reverse('admin:main_room_change', args=[obj.room.id]),
            obj.room.get_room_type_display(),
            obj.room.address)
    room_link.short_description = 'Комната'
    
    def dates_display(self, obj):
        nights = (obj.check_out_date - obj.check_in_date).days
        return format_html('{} — {}<br><small style="color:#666;">{} ночей</small>',
            obj.check_in_date.strftime('%d.%m.%Y'),
            obj.check_out_date.strftime('%d.%m.%Y'),
            nights)
    dates_display.short_description = 'Даты'
    
    def total_cost_display(self, obj):
        return format_html('<strong>{} ₽</strong>', int(obj.total_cost))
    total_cost_display.short_description = 'Сумма'
    
    def status_badge(self, obj):
        colors = {
            'Pending': '#ffc107',
            'Confirmed': '#28a745',
            'Cancelled': '#dc3545',
        }
        text_colors = {
            'Pending': '#000',
            'Confirmed': '#fff',
            'Cancelled': '#fff',
        }
        color = colors.get(obj.status, '#666')
        text_color = text_colors.get(obj.status, '#fff')
        return format_html(
            '<span style="background: {}; color: {}; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, text_color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    actions = ['confirm_bookings', 'cancel_bookings']
    
    @admin.action(description='Подтвердить бронирования')
    def confirm_bookings(self, request, queryset):
        queryset.update(status=BookingStatus.CONFIRMED)
        self.message_user(request, f'{queryset.count()} бронирований подтверждены')
    
    @admin.action(description='Отменить бронирования')
    def cancel_bookings(self, request, queryset):
        queryset.update(status=BookingStatus.CANCELLED)
        self.message_user(request, f'{queryset.count()} бронирований отменены')


# ==================== REVIEW ====================
@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'guest_link', 'room_link', 'rating_display', 'review_preview', 'status_badge', 'has_reply', 'created_at')
    list_filter = ('status', 'rating', 'created_at')
    search_fields = ('guest__email', 'room__address', 'review_text')
    ordering = ('-created_at',)
    list_per_page = 25
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('booking', 'guest', 'room', 'rating', 'review_text')
        }),
        ('Модерация', {
            'fields': ('status', 'moderated_by', 'moderation_comment', 'moderated_at'),
            'classes': ('collapse',)
        }),
        ('Ответ владельца', {
            'fields': ('owner_reply', 'owner_reply_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('moderated_at', 'owner_reply_at')
    
    def guest_link(self, obj):
        return format_html('<a href="{}">{}</a>',
            reverse('admin:main_user_change', args=[obj.guest.id]),
            obj.guest.get_full_name())
    guest_link.short_description = 'Гость'
    
    def room_link(self, obj):
        return format_html('<a href="{}">{} • {}</a>',
            reverse('admin:main_room_change', args=[obj.room.id]),
            obj.room.get_room_type_display(),
            obj.room.address)
    room_link.short_description = 'Комната'
    
    def rating_display(self, obj):
        stars = '⭐' * obj.rating + '☆' * (5 - obj.rating)
        return format_html('<span style="color: #f59e0b;">{}</span>', stars)
    rating_display.short_description = 'Рейтинг'
    
    def review_preview(self, obj):
        if obj.review_text:
            text = obj.review_text[:50] + '...' if len(obj.review_text) > 50 else obj.review_text
            return text
        return format_html('<span style="color: #999;">Без текста</span>')
    review_preview.short_description = 'Отзыв'
    
    def status_badge(self, obj):
        colors = {
            'pending': '#ffc107',
            'approved': '#28a745',
            'rejected': '#dc3545',
        }
        text_colors = {
            'pending': '#000',
            'approved': '#fff',
            'rejected': '#fff',
        }
        color = colors.get(obj.status, '#666')
        text_color = text_colors.get(obj.status, '#fff')
        return format_html(
            '<span style="background: {}; color: {}; padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: bold;">{}</span>',
            color, text_color, obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def has_reply(self, obj):
        if obj.owner_reply:
            return format_html('<span style="color: #28a745;">✓ Есть</span>')
        return format_html('<span style="color: #999;">—</span>')
    has_reply.short_description = 'Ответ'
    
    actions = ['approve_reviews', 'reject_reviews']
    
    @admin.action(description='Одобрить отзывы')
    def approve_reviews(self, request, queryset):
        queryset.update(status=ReviewStatus.APPROVED, moderated_by=request.user)
        self.message_user(request, f'{queryset.count()} отзывов одобрены')
    
    @admin.action(description='Отклонить отзывы')
    def reject_reviews(self, request, queryset):
        queryset.update(status=ReviewStatus.REJECTED, moderated_by=request.user)
        self.message_user(request, f'{queryset.count()} отзывов отклонены')


# ==================== BOOKING HISTORY ====================
@admin.register(BookingHistory)
class BookingHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'booking_link', 'status_change', 'changed_by', 'change_description', 'created_at')
    list_filter = ('new_status', 'created_at')
    search_fields = ('booking__id', 'changed_by', 'change_description')
    ordering = ('-created_at',)
    list_per_page = 25
    
    def booking_link(self, obj):
        return format_html('<a href="{}">Бронирование #{}</a>',
            reverse('admin:main_booking_change', args=[obj.booking.id]),
            obj.booking.id)
    booking_link.short_description = 'Бронирование'
    
    def status_change(self, obj):
        if obj.old_status:
            return format_html('{} → {}', obj.get_old_status_display(), obj.get_new_status_display())
        return obj.get_new_status_display()
    status_change.short_description = 'Изменение статуса'


# ==================== ROOM IMAGE ====================
@admin.register(RoomImage)
class RoomImageAdmin(admin.ModelAdmin):
    list_display = ('id', 'room_link', 'image_preview', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('room__address',)
    ordering = ('-created_at',)
    
    def room_link(self, obj):
        return format_html('<a href="{}">Комната #{}</a>',
            reverse('admin:main_room_change', args=[obj.room.id]),
            obj.room.id)
    room_link.short_description = 'Комната'
    
    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 50px; border-radius: 4px;" />', obj.image.url)
        return '—'
    image_preview.short_description = 'Превью'
