from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth.models import (
	AbstractBaseUser, BaseUserManager, PermissionsMixin
)
from django.contrib.auth.hashers import check_password
from django.db.models import Q


class RoomType(models.TextChoices):
    STANDARD = 'Standard', 'Standard'
    DELUXE = 'Deluxe', 'Deluxe'
    SUITE = 'Suite', 'Suite'

class BookingStatus(models.TextChoices):
    PENDING = 'Pending', 'Pending'
    CONFIRMED = 'Confirmed', 'Confirmed'
    CANCELLED = 'Cancelled', 'Cancelled'

class UserRole(models.TextChoices):
    USER = 'user', 'Пользователь'
    STAFF = 'staff', 'Сотрудник'
    ADMIN = 'admin', 'Администратор'

class RoomManager(models.Manager):
    def get_available_rooms(self, address, check_in_date, check_out_date):
        address_normalized = (address or '').strip()
        if not address_normalized:
            return self.none()

        rooms = (
            self.filter(is_active=True)
            .filter(address__iexact=address_normalized)
        )
        bookings = Booking.objects.filter(
            room__in=rooms,
            check_in_date__lte=check_out_date,
            check_out_date__gte=check_in_date,
            status__in=[BookingStatus.CONFIRMED, BookingStatus.PENDING],
        )
        available_rooms = rooms.exclude(id__in=bookings.values_list('room__id', flat=True))
        return available_rooms.order_by('price_per_night')

class UserManager(BaseUserManager):
    def create_user(self, first_name, last_name, email, phone, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        if not first_name:
            raise ValueError('First name is required')
        if not last_name:
            raise ValueError('Last name is required')
        if not phone:
            raise ValueError('Phone is required')
        if not password:
            raise ValueError('Password is required')
        email = self.normalize_email(email)
        user = self.model(first_name=first_name, last_name=last_name, email=email, phone=phone, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staff(self, first_name, last_name, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('role', UserRole.STAFF)
        user = self.create_user(first_name, last_name, email, phone, password, **extra_fields)
        return user

    def create_superuser(self, first_name, last_name, email, phone, password=None, **extra_fields):
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', UserRole.ADMIN)
        user = self.create_user(first_name, last_name, email, phone, password, **extra_fields)
        return user

class BaseModel(models.Model):
    id = models.AutoField(primary_key=True)
    created_at = models.DateTimeField(auto_now=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20)
    password = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.USER)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'phone']

    def __str__(self):
        return f"{self.first_name} - {self.last_name}"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

    def get_short_name(self):
        return self.first_name

    def get_phone(self):
        return self.phone

    def check_password(self, password):
        return check_password(password, self.password)

    def get_email(self):
        return self.email

    @property
    def is_admin(self):
        return self.role == UserRole.ADMIN or self.is_superuser
    
    @property
    def is_staff(self):
        return self.role in [UserRole.STAFF, UserRole.ADMIN] or self.is_superuser

    @property
    def is_owner(self):
        """Проверяет, есть ли у пользователя комнаты"""
        return self.rooms.exists()

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"

class Room(BaseModel):
    room_owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='rooms', verbose_name="Владелец комнаты")
    room_type = models.CharField(max_length=20, choices=RoomType.choices)
    price_per_night = models.FloatField(validators=[MinValueValidator(100)])
    address = models.CharField()
    room_photo = models.ImageField(upload_to='rooms/', blank=True, null=True, verbose_name="Фото номера")
    is_active = models.BooleanField(default=True)

    capacity = models.IntegerField(default=2, verbose_name="Вместимость (человек)")
    size = models.CharField(max_length=50, blank=True, verbose_name="Размер (м²)")
    amenities = models.TextField(blank=True, verbose_name="Удобства в номере")

    objects = RoomManager()

    def __str__(self):
        return f"Room {self.id} ({self.get_room_type_display()})"

    @property
    def amenities_list(self):
        if not self.amenities:
            return []
        return [item.strip() for item in self.amenities.splitlines() if item.strip()]

    class Meta:
        verbose_name = "Room"
        verbose_name_plural = "Rooms"


class RoomImage(BaseModel):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='rooms/')

    class Meta:
        verbose_name = "Room image"
        verbose_name_plural = "Room images"

    def __str__(self):
        return f"RoomImage {self.id} for Room {self.room_id}"

class Booking(BaseModel):
    guest = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='bookings')
    check_in_date = models.DateField()
    check_out_date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=BookingStatus.choices,
        default=BookingStatus.PENDING
    )
    total_cost = models.FloatField(validators=[MinValueValidator(0)])

    def __str__(self):
        return f"Booking {self.id} - {self.guest} for {self.room}"

    class Meta:
        verbose_name = "Booking"
        verbose_name_plural = "Bookings"
        constraints = [
            models.CheckConstraint(
                check=models.Q(check_in_date__lt=models.F('check_out_date')),
                name='check_dates'
            )
        ]

class BookingHistory(BaseModel):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    old_status = models.CharField(max_length=20, choices=BookingStatus.choices, blank=True)
    new_status = models.CharField(max_length=20, choices=BookingStatus.choices)
    changed_by = models.CharField(max_length=100, default='SYSTEM')
    change_description = models.TextField(blank=True)

    def get_old_status_display(self):
        if not self.old_status:
            return ''
        for value, label in BookingStatus.choices:
            if value == self.old_status:
                return label
        return self.old_status

    def get_new_status_display(self):
        for value, label in BookingStatus.choices:
            if value == self.new_status:
                return label
        return self.new_status

    def __str__(self):
        return f"History {self.id} for Booking {self.booking_id}"

    class Meta:
        verbose_name = "Booking History"
        verbose_name_plural = "Booking Histories"

class ReviewStatus(models.TextChoices):
    PENDING = 'pending', 'На модерации'
    APPROVED = 'approved', 'Одобрен'
    REJECTED = 'rejected', 'Отклонён'

class Review(BaseModel):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    guest = models.OneToOneField(User, on_delete=models.CASCADE)
    room = models.OneToOneField(Room, on_delete=models.CASCADE)
    rating = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    review_text = models.TextField(blank=True)
    
    # Модерация
    status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        verbose_name='Статус модерации'
    )
    moderated_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='moderated_reviews',
        verbose_name='Модератор'
    )
    moderation_comment = models.TextField(blank=True, verbose_name='Комментарий модератора')
    moderated_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата модерации')
    
    # Ответ владельца
    owner_reply = models.TextField(blank=True, verbose_name='Ответ владельца')
    owner_reply_at = models.DateTimeField(null=True, blank=True, verbose_name='Дата ответа')

    def __str__(self):
        return f"Review {self.id} by {self.guest} (Rating: {self.rating})"

    class Meta:
        verbose_name = "Review"
        verbose_name_plural = "Reviews"

