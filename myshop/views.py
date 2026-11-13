
from .models import Customer
from django.shortcuts import render,get_object_or_404,redirect
from .models import Category,Product,Shipping_Address,Order,Cart
from django.core.paginator import Paginator,EmptyPage,PageNotAnInteger

#-------------------------Authorization------------------------------------
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User

def index(request):
    return render(request, "myshop/index.html")

def about(request):
    return render(request, "myshop/about.html")

def contact(request):
    R=0
    A=0
    B=0
    O='+'
    if request.method=="POST":
        A=request.POST.get('A',0)
        B=request.POST.get('B',0)
        O=request.POST.get('O')
        if (O=="+"):
            R=int(A)+int(B)
        elif (O=="-"):
            R=int(A)-int(B)
        elif (O=="*"):
            R=int(A)*int(B)
        elif (O=="/"):
            R=int(A)/int(B)
        else:
            R=0     

    context={
        'A':A,
        'B':B,
        'O':O,
        'R':R
    }
    return render(request, "myshop/contact.html",context)

def shop(request):

    category=Category.objects.all().order_by("id")

    if request.method=='POST':
        keyword=request.POST.get('search')
        product=Product.objects.filter(product_name__icontains=keyword).order_by("id")
    else:
        product=Product.objects.all().order_by("id")
    
    item_per_page=5
    paginator=Paginator(product,item_per_page)
    page_number=request.GET.get('page',1)

    try:
        page_obj=paginator.page(page_number)
    except PageNotAnInteger:
        page_obj=paginator.page(1)
    except EmptyPage:
        page_obj=paginator.page(1)

    context={
        "category":category,
        "product":page_obj
    }

    return render(request, "myshop/shop.html", context)

def shopdetail(request,id):

    product=get_object_or_404(Product,pk=id)

    context={
        "product":product
    }

    return render(request, "myshop/shopdetail.html",context)

#-------------------------------Add To Cart----------------------------------

def add_to_cart(request,id):
    product_id=str(id)
    qty=request.POST.get('qty',1)

    cart_item={
        'id':product_id,
        'quantity':qty
    }
    if request.session.get('cart'):
        cart=request.session['cart']
        if product_id in cart:
            oldQty=cart[product_id]['quantity']
            NewQty=int(oldQty)+int(qty)
            cart[product_id]['quantity'] = NewQty
        else:
            cart[product_id]=cart_item

        request.session.modified=True  

    else:
        cart={
            id:cart_item
        }
        request.session['cart']=cart

    return redirect('cart')


def cart(request):

    cart_items=[]
    cart=request.session.get('cart',{})
    cart_total=0

    for item in cart.values():
        product=Product.objects.get(pk=item['id'])
        total=int(item['quantity'])*product.price
        cart_total += total

        cart_items.append(
            {
                'product':product,
                'total':total,
                'quantity':item['quantity']
            }
        )

    context={
        'cart_items':cart_items,
        'cart_total':cart_total,
        'cart_sub_total':cart_total+15
    }    

    return render(request, "myshop/cart.html",context)

def remove_from_cart(request,id):

    product_id=str(id)
    cart=request.session.get('cart',{})

    if product_id in cart:
        del cart[product_id]                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         
        request.session['cart']=cart

    return redirect('cart')

@login_required(login_url='login')
def checkout(request):

    cart_items=[]
    cart=request.session.get('cart',{})
    cart_total=0
    msg=""


    for item in cart.values():
        product=Product.objects.get(pk=item['id'])
        total=int(item['quantity'])*product.price
        cart_total += total
        

        cart_items.append(
            {
                'product':product,
                'total':total,
                'quantity':item['quantity']
            }
        )

    if request.method=="POST":
        full_name=request.POST['full_name']
        address=request.POST['address']
        city=request.POST['city']
        country=request.POST['country']
        state=request.POST['state']
        zip_code=request.POST['zip_code']

        user_r=request.user

        shipped=Shipping_Address.objects.create(contact=full_name,shipping_address=address,shipping_city=city,shipping_country=country,shipping_state=state,shipping_zip_code=zip_code,user=user_r)
        order=Order.objects.create(user=user_r,shipped=shipped,total_qty=cart_total,total_cost=cart_total)

        for item in cart.values():
                product=Product.objects.get(pk=item['id'])
                total=int(item['quantity'])*product.price
  
                cart=Cart.objects.create(user=user_r,order=order,product=product,quantity=item['quantity'],price=product.price)      

        msg="Your Cart and Order has been saved"                        

    context={
        'cart_items':cart_items,
        'cart_total':cart_total,
        'cart_sub_total':cart_total+15,
        'msg':msg
    }    

    return render(request, "myshop/checkout.html",context)


def signup(request):
    msg=""

    if request.method=="POST":
        first_name=request.POST['firstname']
        username=request.POST['username']
        email=request.POST['email']
        password=request.POST['password']

        if User.objects.filter(username=username).exists():
            msg="User already exist plz choose different"
        else:
            user=User.objects.create_user(first_name=first_name,username=username,email=email,password=password)
            user.save()
            msg="Your registration has been completed plz login"

    context={
        'msg':msg
    }

    return render(request, "myshop/signup.html",context)



def login_view(request):
    msg=""

    if request.method=="POST":
        username=request.POST.get('username')
        password=request.POST.get('password')
        user=authenticate(request,username=username,password=password)

        if user is not None:
            login(request,user)
            next_param=request.GET.get('next')

            if next_param:
                return redirect(next_param)
            else:
                return redirect('index')
        else:
            msg="Invalid user name or password"    

    context={
        "msg":msg
    }
    return render(request, "myshop/login.html",context)

#-----------------------AI/ML----------------------------------
from django.http import HttpResponse
import pandas as pd
import os
from django.conf import settings
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.http import HttpResponse,JsonResponse


def realEstateSearch(request):

    excel_file=os.path.join('media','world_real_estate_data.xls')
    data=pd.DataFrame()
    results=None
    results_list=[]

    try:
        data=pd.read_excel(excel_file)
        results=data[['property_type','location','city','province_name','price','area','agent','agency','purpose']]

        results_list=results.astype(str).to_dict(orient='records')

    except Exception as e:    
        return HttpResponse("error occured {e}")

    if request.method=="POST":
        search=request.POST.get('search','')
        results=results[results['location'].astype(str).str.contains(search,case=False,na=False)]
        results_list=results.astype(str).to_dict(orient='records')

    if request.method=="GET":
           type=request.GET.get('type','')
           results=results[results['property_type'].astype(str).str.contains(type,case=False,na=False)]
           results_list=results.astype(str).to_dict(orient='records')

    #-----------------pagination----------------------
    page=request.GET.get('page',1)
    paginator=Paginator(results_list,20)
    results_page=paginator.page(page)

    context={
        'results_list':results_page
    }

    return render(request, "myshop/realestatesearch.html",context)    


def realEstateGraph(request):

    excel_file=os.path.join('media','world_real_estate_data.xls')
    data=pd.DataFrame()
    results=None
    results_list=[]

    try:
        data=pd.read_excel(excel_file)
        results=data[['property_type','location','city','province_name','price','area','agent','agency','purpose']]

        data['price']=pd.to_numeric(data['price'],errors='coerce')
        data.dropna(subset=['price'],inplace=True)

        if data.empty:
            return JsonResponse(
                {
                    'error':'price data not found'
                }
            )

        city_prices=data.groupby('city')['price'].mean().sort_values(ascending=False)

        city_prices_dict={
            city:round(price,2)
            for city,price in city_prices.items()
        }

    except Exception as e:    
        return HttpResponse("error occured {e}")

    chart_data={
        'labels':list(city_prices_dict.keys()),
        'datasets':[{
            'label':'City wise average price',
            'data':list(city_prices_dict.values())
        }]
    }

    return JsonResponse(chart_data)    


def JQUERYGraph(request):
    return render(request, "myshop/jquery1.html")


def realEstateGraphbycity(request):

    excel_file=os.path.join('media','world_real_estate_data.xls')
    data=pd.DataFrame()
    
    try:
        data=pd.read_excel(excel_file)
       
        if request.method=="GET":                   
            city=request.GET.get('city','')
            data=data[data['city'].astype(str).str.contains(city,case=False,na=False)]
           
        data['price']=pd.to_numeric(data['price'],errors='coerce')
        data.dropna(subset=['price'],inplace=True)

        if data.empty:
            return JsonResponse(
                {
                    'error':'price data not found'
                }
            )

        location_prices=data.groupby('location')['price'].mean().sort_values(ascending=False)

        location_dict={
            city:round(price,2)
            for city,price in location_prices.items()
        }

    except Exception as e:    
        return HttpResponse("error occured {e}")

    chart_data={
        'labels':list(location_dict.keys()),
        'datasets':[{
            'label':'Location wise average price',
            'data':list(location_dict.values())
        }]
    }

    return JsonResponse(chart_data)    


def realEstatePredictionGraphbycity(request):

    excel_file=os.path.join('media','world_real_estate_data.xls')
    data=pd.DataFrame()
    
    try:
        data=pd.read_excel(excel_file)
       
        if request.method=="GET":                   
            city=request.GET.get('city','')
            data=data[data['city'].astype(str).str.contains(city,case=False,na=False)]
           
        data['price']=pd.to_numeric(data['price'],errors='coerce')
        data.dropna(subset=['price'],inplace=True)

        if data.empty:
            return JsonResponse(
                {
                    'error':'price data not found'
                }
            )

        location_prices=data.groupby('location')['price'].mean().sort_values(ascending=False)

        location_dict={
            city:round(price,2)
            for city,price in location_prices.items()
        }

    except Exception as e:    
        return HttpResponse("error occured {e}")

    chart_data={
        'labels':list(location_dict.keys()),
        'datasets':[{
            'label':'Location wise average price',
            'data':list(location_dict.values())
        }]
    }

    return JsonResponse(chart_data)    

#--------------------AI/ML------------------------------

import os
import pandas as pd
import plotly.offline as opy
import plotly.graph_objects as go
import plotly.express as px
from django.http import HttpResponse
from django.shortcuts import render

from django.shortcuts import render
from django.http import HttpResponse, JsonResponse
import pandas as pd
import os
import plotly.graph_objects as go

import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.offline as opy

from django.http import JsonResponse, HttpResponse
from django.shortcuts import render


def realEstatePrediction(request):

    excel_file = os.path.join(
        'media',
        'world_real_estate_data.xls'
    )

    try:
        # ==========================================
        # READ EXCEL FILE
        # ==========================================
        data = pd.read_excel(excel_file)

        # ==========================================
        # CHECK REQUIRED COLUMNS
        # ==========================================
        required_columns = [
            'price',
            'city'
        ]

        for column in required_columns:
            if column not in data.columns:
                return JsonResponse({
                    'error': f'Column "{column}" not found in Excel file'
                })

        # ==========================================
        # CLEAN DATA
        # ==========================================
        data['price'] = pd.to_numeric(
            data['price'],
            errors='coerce'
        )

        data['city'] = data['city'].astype(str).str.strip()

        # Remove invalid records
        data.dropna(
            subset=['price', 'city'],
            inplace=True
        )

        data = data[data['city'] != '']

        if data.empty:
            return JsonResponse({
                'error': 'Price data not found'
            })

        # ==========================================
        # CITY-WISE AVERAGE PRICE
        # ==========================================
        city_prices = (
            data.groupby('city')['price']
            .mean()
            .reset_index()
        )

        city_prices = city_prices.sort_values(
            by='price',
            ascending=False
        )

        # ==========================================
        # 1. BAR CHART
        # ==========================================
        fig_bar = go.Figure()

        fig_bar.add_trace(
            go.Bar(
                x=city_prices['city'],
                y=city_prices['price'],
                name='Average Price',
                text=city_prices['price'].round(0),
                textposition='auto'
            )
        )

        fig_bar.update_layout(
            title='Average Real Estate Price by City',
            xaxis_title='City',
            yaxis_title='Average Price',
            template='plotly_white',
            height=500
        )

        BarChart_Div = opy.plot(
            fig_bar,
            auto_open=False,
            output_type='div'
        )

        # ==========================================
        # 2. PIE CHART
        # ==========================================
        city_count = (
            data.groupby('city')
            .size()
            .reset_index(name='property_count')
        )

        # Sort
        city_count = city_count.sort_values(
            by='property_count',
            ascending=False
        )

        # Optional: show top 10 cities
        pie_data = city_count.head(10)

        fig_pie = go.Figure(
            data=[
                go.Pie(
                    labels=pie_data['city'],
                    values=pie_data['property_count'],
                    hole=0.3
                )
            ]
        )

        fig_pie.update_layout(
            title='Property Distribution by City',
            template='plotly_white',
            height=500
        )

        PieChart_Div = opy.plot(
            fig_pie,
            auto_open=False,
            output_type='div'
        )

        # ==========================================
        # 3. LINE CHART
        # ==========================================
        fig_line = go.Figure()

        fig_line.add_trace(
            go.Scatter(
                x=city_prices['city'],
                y=city_prices['price'],
                mode='lines+markers',
                name='Average Price'
            )
        )

        fig_line.update_layout(
            title='Average Real Estate Price by City',
            xaxis_title='City',
            yaxis_title='Average Price',
            template='plotly_white',
            height=500
        )

        LineChart_Div = opy.plot(
            fig_line,
            auto_open=False,
            output_type='div'
        )

        # ==========================================
        # 4. MAP CHART
        # ==========================================
        MapChart_Div = None

        # Check whether latitude and longitude exist
        if 'latitude' in data.columns and 'longitude' in data.columns:

            data['latitude'] = pd.to_numeric(
                data['latitude'],
                errors='coerce'
            )

            data['longitude'] = pd.to_numeric(
                data['longitude'],
                errors='coerce'
            )

            map_data = data.dropna(
                subset=[
                    'latitude',
                    'longitude',
                    'price'
                ]
            )

            if not map_data.empty:

                fig_map = px.scatter_map(
                    map_data,
                    lat='latitude',
                    lon='longitude',
                    color='price',
                    size='price',
                    hover_name='city',
                    hover_data={
                        'price': True,
                        'latitude': False,
                        'longitude': False
                    },
                    zoom=4,
                    height=600,
                    title='Real Estate Price Location Map'
                )

                fig_map.update_layout(
                    map_style='open-street-map',
                    margin={
                        'l': 0,
                        'r': 0,
                        't': 50,
                        'b': 0
                    }
                )

                MapChart_Div = opy.plot(
                    fig_map,
                    auto_open=False,
                    output_type='div'
                )

        # ==========================================
        # CONTEXT
        # ==========================================
        context = {
            'BarChart_Div': BarChart_Div,
            'PieChart_Div': PieChart_Div,
            'LineChart_Div': LineChart_Div,
            'MapChart_Div': MapChart_Div
        }

        return render(
            request,
            'myshop/realEstatePrediction.html',
            context
        )

    except Exception as e:

        return HttpResponse(
            f"Error occurred: {e}"
        )


import os
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import plotly.offline as opy

from django.shortcuts import render
from django.http import HttpResponse


def realEstatePrediction2(request):

    excel_file = os.path.join(
        'media',
        'world_real_estate_data.xls'
    )

    try:

        # =====================================================
        # READ EXCEL FILE
        # =====================================================

        data = pd.read_excel(excel_file)

        # =====================================================
        # REQUIRED COLUMNS
        # =====================================================

        required_columns = [
            'price',
            'city',
            'location'
        ]

        for column in required_columns:

            if column not in data.columns:

                return HttpResponse(
                    f'Column "{column}" not found in Excel file'
                )

        # =====================================================
        # CLEAN DATA
        # =====================================================

        data['price'] = pd.to_numeric(
            data['price'],
            errors='coerce'
        )

        data['city'] = (
            data['city']
            .astype(str)
            .str.strip()
        )

        data['location'] = (
            data['location']
            .astype(str)
            .str.strip()
        )

        data.dropna(
            subset=[
                'price',
                'city',
                'location'
            ],
            inplace=True
        )

        data = data[
            (data['city'] != '') &
            (data['location'] != '')
        ]

        if data.empty:

            return HttpResponse(
                'No valid real estate data found.'
            )

        # =====================================================
        # CITY DROPDOWN
        # =====================================================

        cities = sorted(
            data['city']
            .dropna()
            .unique()
            .tolist()
        )

        # =====================================================
        # SELECT CITY
        # =====================================================

        selected_city = request.GET.get(
            'city',
            ''
        ).strip()

        # =====================================================
        # DEFAULT: FIRST CITY
        # =====================================================

        if not selected_city and cities:

            selected_city = cities[0]

        # =====================================================
        # FILTER SELECTED CITY
        # =====================================================

        city_data = data[
            data['city'] == selected_city
        ].copy()

        # =====================================================
        # 1. CITY-WISE AVERAGE PRICE BAR CHART
        # =====================================================

        city_prices = (
            data.groupby('city')['price']
            .mean()
            .reset_index()
        )

        city_prices = city_prices.sort_values(
            by='price',
            ascending=False
        )

        fig_bar_city = go.Figure()

        fig_bar_city.add_trace(
            go.Bar(
                x=city_prices['city'],
                y=city_prices['price'],
                text=city_prices['price'].round(0),
                textposition='auto',
                name='Average Price'
            )
        )

        fig_bar_city.update_layout(
            title='Average Property Price by City',
            xaxis_title='City',
            yaxis_title='Average Price',
            template='plotly_white',
            height=500
        )

        CityBarChart_Div = opy.plot(
            fig_bar_city,
            auto_open=False,
            output_type='div'
        )

        # =====================================================
        # 2. CITY PROPERTY DISTRIBUTION PIE CHART
        # =====================================================

        city_count = (
            data.groupby('city')
            .size()
            .reset_index(
                name='property_count'
            )
        )

        city_count = city_count.sort_values(
            by='property_count',
            ascending=False
        )

        fig_city_pie = go.Figure(
            data=[
                go.Pie(
                    labels=city_count['city'],
                    values=city_count['property_count'],
                    hole=0.3
                )
            ]
        )

        fig_city_pie.update_layout(
            title='Property Distribution by City',
            template='plotly_white',
            height=500
        )

        CityPieChart_Div = opy.plot(
            fig_city_pie,
            auto_open=False,
            output_type='div'
        )

        # =====================================================
        # 3. LOCATION-WISE AVERAGE PRICE
        # =====================================================

        location_prices = (
            city_data
            .groupby('location')['price']
            .mean()
            .reset_index()
        )

        location_prices = location_prices.sort_values(
            by='price',
            ascending=False
        )

        # =====================================================
        # LOCATION BAR CHART
        # =====================================================

        fig_location_bar = go.Figure()

        fig_location_bar.add_trace(
            go.Bar(
                x=location_prices['location'],
                y=location_prices['price'],
                text=location_prices['price'].round(0),
                textposition='auto',
                name='Average Price'
            )
        )

        fig_location_bar.update_layout(
            title=f'Average Property Price by Location - {selected_city}',
            xaxis_title='Location',
            yaxis_title='Average Price',
            template='plotly_white',
            height=550
        )

        LocationBarChart_Div = opy.plot(
            fig_location_bar,
            auto_open=False,
            output_type='div'
        )

        # =====================================================
        # 4. LOCATION PIE CHART
        # =====================================================

        location_count = (
            city_data
            .groupby('location')
            .size()
            .reset_index(
                name='property_count'
            )
        )

        location_count = location_count.sort_values(
            by='property_count',
            ascending=False
        )

        fig_location_pie = go.Figure(
            data=[
                go.Pie(
                    labels=location_count['location'],
                    values=location_count['property_count'],
                    hole=0.3
                )
            ]
        )

        fig_location_pie.update_layout(
            title=f'Property Distribution by Location - {selected_city}',
            template='plotly_white',
            height=550
        )

        LocationPieChart_Div = opy.plot(
            fig_location_pie,
            auto_open=False,
            output_type='div'
        )

        # =====================================================
        # 5. LOCATION-WISE LINE CHART
        # =====================================================

        fig_location_line = go.Figure()

        fig_location_line.add_trace(
            go.Scatter(
                x=location_prices['location'],
                y=location_prices['price'],
                mode='lines+markers',
                name='Average Price'
            )
        )

        fig_location_line.update_layout(
            title=f'Location-wise Average Price - {selected_city}',
            xaxis_title='Location',
            yaxis_title='Average Price',
            template='plotly_white',
            height=500
        )

        LocationLineChart_Div = opy.plot(
            fig_location_line,
            auto_open=False,
            output_type='div'
        )

        # =====================================================
        # 6. MAP
        # =====================================================

        MapChart_Div = None

        if (
            'latitude' in city_data.columns and
            'longitude' in city_data.columns
        ):

            city_data['latitude'] = pd.to_numeric(
                city_data['latitude'],
                errors='coerce'
            )

            city_data['longitude'] = pd.to_numeric(
                city_data['longitude'],
                errors='coerce'
            )

            map_data = city_data.dropna(
                subset=[
                    'latitude',
                    'longitude'
                ]
            )

            if not map_data.empty:

                fig_map = px.scatter_map(
                    map_data,
                    lat='latitude',
                    lon='longitude',
                    color='price',
                    size='price',
                    hover_name='location',
                    hover_data={
                        'city': True,
                        'location': True,
                        'price': True,
                        'latitude': False,
                        'longitude': False
                    },
                    zoom=10,
                    height=600,
                    title=f'Real Estate Locations - {selected_city}'
                )

                fig_map.update_layout(
                    map_style='open-street-map',
                    margin={
                        'l': 0,
                        'r': 0,
                        't': 50,
                        'b': 0
                    }
                )

                MapChart_Div = opy.plot(
                    fig_map,
                    auto_open=False,
                    output_type='div'
                )

        # =====================================================
        # CONTEXT
        # =====================================================

        context = {

            'cities': cities,

            'selected_city': selected_city,

            'CityBarChart_Div':
                CityBarChart_Div,

            'CityPieChart_Div':
                CityPieChart_Div,

            'LocationBarChart_Div':
                LocationBarChart_Div,

            'LocationPieChart_Div':
                LocationPieChart_Div,

            'LocationLineChart_Div':
                LocationLineChart_Div,

            'MapChart_Div':
                MapChart_Div,

        }

        return render(
            request,
            'myshop/realEstatePrediction2.html',
            context
        )

    except Exception as e:

        return HttpResponse(
            f'Error occurred: {e}'
        )    