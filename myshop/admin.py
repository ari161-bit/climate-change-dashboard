from django.contrib import admin

from .models import Customer,Supplier,Category,Product,Shipping_Address,Order,Cart

admin.site.register(Customer)

admin.site.register(Supplier)

admin.site.register(Category)

admin.site.register(Product)

admin.site.register(Shipping_Address)

admin.site.register(Order)

admin.site.register(Cart)