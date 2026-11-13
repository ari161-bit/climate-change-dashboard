from django.db import models
import datetime
from django.utils import timezone
from django.contrib.auth.models import User

class Customer(models.Model):
    id = models.AutoField(primary_key=True,)
    full_name = models.CharField(max_length=100, null=True)
    first_name = models.CharField(max_length=100, null=True)
    username = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=50)
    password = models.CharField(max_length=50)
    address = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=50, null=True)
    state = models.CharField(max_length=50, null=True)
    country = models.CharField(max_length=50, null=True)
    zip_code = models.CharField(max_length=10, null=True)

    def __str__(self):
        return self.full_name

class Supplier(models.Model):
    id = models.AutoField(primary_key=True,)
    supplier_name = models.CharField(max_length=100, null=True)  
    address = models.CharField(max_length=100, null=True)
    city = models.CharField(max_length=50, null=True)
    state = models.CharField(max_length=50, null=True)
    country = models.CharField(max_length=50, null=True)
    zip_code = models.CharField(max_length=10, null=True)

    def __str__(self):
        return self.supplier_name
    

class Category(models.Model):
    id = models.AutoField(primary_key=True,)
    category_name = models.CharField(max_length=100, null=True)  
    description = models.CharField(max_length=400, null=True)
    
    image=models.ImageField(
        upload_to='category_images/',
        blank=True,
        null=True
        )

    def __str__(self):
        return f"{self.id} {self.category_name} {self.description}"

class Product(models.Model):

    lorem="Lorem Ipsum is simply dummy text of the printing and typesetting industry. Lorem Ipsum has been the industry's standard dummy text ever since 1966, when designers at Letraset and James Mosley, the librarian at St Bride Printing Library in London, took a 1914 Cicero translation and scrambled it to make dummy text for Letraset's Body Type sheets. It has survived not only many decades, but also the leap into electronic typesetting, remaining essentially unchanged. It was popularised thanks to these sheets and more recently with desktop publishing software like Aldus PageMaker and Microsoft Word including versions of Lorem Ipsum."

    id = models.AutoField(primary_key=True,)
    product_name = models.CharField(max_length=100, null=True)

    description = models.TextField(default=lorem)

    product_category=models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        default=1
    )
    
    image=models.ImageField(
        upload_to='product_images/'
        )
    
    price=models.DecimalField(
        max_digits=10,
        decimal_places=2
        )

    rooms=models.IntegerField(default=2)
    bath=models.IntegerField(default=2)
    beds=models.IntegerField(default=2)
    area = models.TextField(default="120 sqft")

    def __str__(self):
        return f"{self.id} {self.product_name} {self.description}"            

class Shipping_Address(models.Model):
   
    id = models.AutoField(primary_key=True,)
    order_date=models.DateTimeField(auto_now_add=True)
    contact=models.CharField(max_length=14,null=True)
    shipping_address=models.CharField(max_length=100,null=True)
    shipping_city=models.CharField(max_length=50,null=True)
    shipping_state=models.CharField(max_length=50,null=True)
    shipping_country=models.CharField(max_length=50,null=True)
    shipping_zip_code=models.CharField(max_length=10,null=True)

    user=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        default=1
    )
    
    def __str__(self):
        return f"{self.id} {self.order_date} {self.contact}"

class Order(models.Model):

    STATUS_CHOICES=[
            ('pending','Pending'),
            ('processing','Processing'),
            ('shipped','Shipped'),
            ('delivered','Delivered'),
           ]
   
    id = models.AutoField(primary_key=True,)
    order_date=models.DateTimeField(auto_now_add=True)   

    user=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        default=1
    )

    shipped=models.ForeignKey(
            Shipping_Address,
            on_delete=models.CASCADE,
            default=1
        )

    total_qty=models.PositiveIntegerField(null=True)
    total_cost=models.PositiveIntegerField(null=True)

    status=models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Pending'
    )
    
    def __str__(self):
        return f"{self.id} {self.order_date} {self.shipped.contact}"

class Cart(models.Model):

    id = models.AutoField(primary_key=True,)
    cart_date=models.DateTimeField(auto_now_add=True)   

    user=models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        default=1
    )

    order=models.ForeignKey(
            Order,
            on_delete=models.CASCADE,
            default=1
        )

    product=models.ForeignKey(
                Product,
                on_delete=models.CASCADE,
                default=1
            )

    quantity=models.PositiveIntegerField(null=True)
    price=models.PositiveIntegerField(null=True)

        
    def __str__(self):
        return f"{self.id} {self.order.order_date} {self.product.product_name} {self.quantity} {self.price}"                                                