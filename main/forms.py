import re

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from .models import Room, User, Booking, Review



class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    phone = forms.CharField(required=True)

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'password1', 'password2']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data['phone']
        if commit:
            user.save()
        return user

class UserLoginForm(forms.Form):
    email = forms.EmailField(required=True)
    password = forms.CharField(required=True, widget=forms.PasswordInput)


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone']


class PasswordChangeForm(forms.Form):
    current_password = forms.CharField(required=True, widget=forms.PasswordInput)
    new_password = forms.CharField(required=True, widget=forms.PasswordInput)
    confirm_password = forms.CharField(required=True, widget=forms.PasswordInput)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current_password(self):
        current_password = self.cleaned_data.get('current_password')
        if current_password and not self.user.check_password(current_password):
            raise forms.ValidationError("Неверный текущий пароль.")
        return current_password

    def clean_new_password(self):
        new_password = self.cleaned_data.get('new_password')
        if new_password and len(new_password) < 8:
            raise forms.ValidationError("Пароль должен содержать минимум 8 символов.")
        return new_password

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get('new_password')
        confirm_password = cleaned_data.get('confirm_password')
        if new_password and confirm_password and new_password != confirm_password:
            self.add_error('confirm_password', "Пароли должны совпадать.")
        return cleaned_data


class AvailabilitySearchForm(forms.Form):
    destination = forms.CharField(label='Город или отель', max_length=150)
    check_in = forms.DateField(
        label='Дата заезда',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    check_out = forms.DateField(
        label='Дата выезда',
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    guests = forms.IntegerField(label='Гостей', min_value=1, max_value=8, initial=2)

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in')
        check_out = cleaned_data.get('check_out')

        if check_in and check_in < timezone.localdate():
            self.add_error('check_in', 'Дата заезда не может быть в прошлом.')

        if check_in and check_out and check_in >= check_out:
            self.add_error('check_out', 'Дата выезда должна быть позже даты заезда.')

        return cleaned_data

class RoomCreateForm(forms.ModelForm):
    amenities = forms.CharField(
        label='Удобства в номере',
        required=False,
        widget=forms.Textarea(
            attrs={
                'class': 'form-control',
                'placeholder': 'Например: Wi-Fi, Завтрак, Бассейн',
                'rows': 3,
            }
        ),
        help_text='Перечислите удобства через запятую или с новой строки.',
    )

    class Meta:
        model = Room
        fields = [
            'room_type',
            'price_per_night',
            'address',
            'room_photo',
            'capacity',
            'size',
            'amenities',
        ]
        labels = {
            'room_type': 'Тип комнаты',
            'price_per_night': 'Цена за ночь (₽)',
            'address': 'Город',
            'room_photo': 'Фото номера',
            'capacity': 'Вместимость (человек)',
            'size': 'Размер (м²)',
            'amenities': 'Удобства в номере',
        }
        widgets = {
            'room_type': forms.Select(attrs={'class': 'form-control'}),
            'price_per_night': forms.NumberInput(attrs={'class': 'form-control', 'min': '100', 'step': '0.01'}),
            'address': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: Москва'}),
            'room_photo': forms.FileInput(attrs={'class': 'form-control'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'size': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'например, 25 м²'}),
        }

    def clean_amenities(self):
        amenities_raw = self.cleaned_data.get('amenities', '')
        if not amenities_raw:
            return ''
        parts = re.split(r'[\n,]+', amenities_raw)
        normalized = [item.strip() for item in parts if item.strip()]
        return '\n'.join(normalized)


class RoomUpdateForm(RoomCreateForm):
    class Meta(RoomCreateForm.Meta):
        pass

class BookingCreateForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['check_in_date', 'check_out_date']
        labels = {
            'check_in_date': 'Дата заезда',
            'check_out_date': 'Дата выезда',
        }
        widgets = {
            'check_in_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': timezone.localdate().isoformat()
                }
            ),
            'check_out_date': forms.DateInput(
                attrs={
                    'type': 'date',
                    'class': 'form-control',
                    'min': timezone.localdate().isoformat()
                }
            ),
        }

    def clean_check_in_date(self):
        check_in = self.cleaned_data.get('check_in_date')
        if check_in and check_in < timezone.localdate():
            raise forms.ValidationError('Дата заезда не может быть в прошлом.')
        return check_in

    def clean(self):
        cleaned_data = super().clean()
        check_in = cleaned_data.get('check_in_date')
        check_out = cleaned_data.get('check_out_date')
        room = cleaned_data.get('room')

        if check_in and check_out:
            if check_in >= check_out:
                raise forms.ValidationError({
                    'check_out_date': 'Дата выезда должна быть позже даты заезда.'
                })

            # Проверка доступности комнаты будет выполнена в view

        return cleaned_data

class BookingUpdateForm(BookingCreateForm):
    class Meta(BookingCreateForm.Meta):
        pass


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'review_text']
        labels = {
            'rating': 'Оценка',
            'review_text': 'Отзыв',
        }
        widgets = {
            'rating': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5'}),
            'review_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class ReviewReplyForm(forms.ModelForm):
    """Форма для ответа владельца на отзыв"""
    class Meta:
        model = Review
        fields = ['owner_reply']
        labels = {
            'owner_reply': 'Ваш ответ',
        }
        widgets = {
            'owner_reply': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Напишите ответ на отзыв гостя...'
            }),
        }


class ReviewModerationForm(forms.ModelForm):
    """Форма для модерации отзыва (staff/admin)"""
    class Meta:
        model = Review
        fields = ['status', 'moderation_comment']
        labels = {
            'status': 'Статус',
            'moderation_comment': 'Комментарий модератора',
        }
        widgets = {
            'status': forms.Select(attrs={'class': 'form-control'}),
            'moderation_comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Причина отклонения (необязательно)...'
            }),
        }