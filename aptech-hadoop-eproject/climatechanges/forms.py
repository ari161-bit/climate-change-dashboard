from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Customer


OPTIONAL = ["first_name", "address", "city", "state", "country", "zip_code"]


class _OptionalFieldsMixin:
    """Address details are optional on sign-up and profile."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in OPTIONAL:
            if name in self.fields:
                self.fields[name].required = False


class CreateUserForm(UserCreationForm):
    """The login account: username + email + password1/password2 (validated by Django)."""
    email = forms.EmailField(max_length=50, required=True)
    first_name = forms.CharField(max_length=100, required=False)

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "password1", "password2"]

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("This email address is already registered.")
        return email


class CustomerRegistrationForm(_OptionalFieldsMixin, forms.ModelForm):
    """The customer profile saved alongside the account."""
    class Meta:
        model = Customer
        fields = ["full_name", "first_name", "address", "city", "state", "country", "zip_code"]

    def clean_full_name(self):
        name = (self.cleaned_data.get("full_name") or "").strip()
        if not name:
            raise forms.ValidationError("Please enter your full name.")
        return name


class ProfileUpdateForm(_OptionalFieldsMixin, forms.ModelForm):
    """Lets a logged-in user edit their profile."""
    class Meta:
        model = Customer
        fields = ["full_name", "first_name", "email", "address", "city", "state", "country", "zip_code"]
        widgets = {f: forms.TextInput(attrs={"placeholder": f.replace("_", " ").title()})
                   for f in ["full_name", "first_name", "address", "city", "state", "country", "zip_code"]}


# ---------------------------------------------------------------------------
# Console forms
# ---------------------------------------------------------------------------
from .models import AlertRule, Dataset, Feedback


class DatasetUploadForm(forms.Form):
    file = forms.FileField(help_text="CSV or JSON tables, or GeoTIFF satellite imagery; up to 20 MB")
    name = forms.CharField(max_length=150, required=False)
    kind = forms.ChoiceField(choices=Dataset.KINDS)
    description = forms.CharField(widget=forms.Textarea(attrs={"rows": 2}), required=False, max_length=1000)


class AlertRuleForm(forms.ModelForm):
    class Meta:
        model = AlertRule
        fields = ["name", "variable", "operator", "threshold", "severity", "active"]


class SupportRequestForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["kind", "subject", "message"]
        widgets = {"message": forms.Textarea(attrs={"rows": 5})}

    def clean_message(self):
        msg = self.cleaned_data["message"].strip()
        if len(msg) < 5:
            raise forms.ValidationError("Please describe the request in a few words.")
        return msg


class SupportReplyForm(forms.ModelForm):
    class Meta:
        model = Feedback
        fields = ["status", "admin_reply"]
        widgets = {"admin_reply": forms.Textarea(attrs={"rows": 4})}
