import os

import pandas as pd
from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render

EXCEL_FILE = os.path.join(settings.BASE_DIR, 'media', 'world_real_estate_data.xls')
# Pre-cleaned subset of the sheet for the 4 dashboard cities; delete it to regenerate from the .xls.
DASHBOARD_CACHE_FILE = os.path.join(settings.BASE_DIR, 'myshop', 'data', 'dashboard_base.csv.gz')


# ---------------- Dashboard: 3D Pie / 3D Bar / Map ----------------

def realEstateDashboard(request):
    return render(request, "myshop/realEstateDashboard.html", {
        'GOOGLE_MAPS_API_KEY': settings.GOOGLE_MAPS_API_KEY,
    })


_dashboard_base_cache = None


def _load_dashboard_base():
    """Load + clean the real-estate sheet once per server process and cache it.

    Re-parsing a 65k-row .xls on every dashboard/filter request made each
    interaction take several seconds; the underlying file doesn't change at
    runtime, so a simple in-memory cache is safe here.
    """
    global _dashboard_base_cache

    if _dashboard_base_cache is not None:
        return _dashboard_base_cache.copy()

    target_cities = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi']

    if os.path.exists(DASHBOARD_CACHE_FILE):
        base = pd.read_csv(DASHBOARD_CACHE_FILE)
        _dashboard_base_cache = base
        return base.copy()

    data = pd.read_excel(EXCEL_FILE)

    base = data[
        ['price', 'location', 'city', 'latitude', 'longitude', 'property_type', 'purpose',
         'bedrooms', 'baths', 'Area Size', 'Area Type']
    ].copy()

    base['price'] = pd.to_numeric(base['price'], errors='coerce')
    base['bedrooms'] = pd.to_numeric(base['bedrooms'], errors='coerce')
    base['baths'] = pd.to_numeric(base['baths'], errors='coerce')
    base.dropna(subset=['price', 'latitude', 'longitude', 'city'], inplace=True)
    base = base[base['city'].isin(target_cities)]

    # normalise every plot size to Marla (1 Kanal = 20 Marla) so price-per-unit-area is comparable
    area_size = pd.to_numeric(base['Area Size'], errors='coerce')
    kanal_to_marla = base['Area Type'].astype(str).str.strip().eq('Kanal').map({True: 20, False: 1})
    base['area_marla'] = area_size * kanal_to_marla

    try:
        os.makedirs(os.path.dirname(DASHBOARD_CACHE_FILE), exist_ok=True)
        base.to_csv(DASHBOARD_CACHE_FILE, index=False)
    except OSError:
        pass

    _dashboard_base_cache = base
    return base.copy()


def realEstateDashboardData(request):

    target_cities = ['Karachi', 'Lahore', 'Islamabad', 'Rawalpindi']

    try:
        base = _load_dashboard_base()

        if base.empty:
            return JsonResponse({'ERROR': 'NO VALID DATA'}, status=400)

        # ---- options available to the filter bar, from the FULL unfiltered dataset ----
        all_types = sorted(base['property_type'].astype(str).unique().tolist())
        price_bounds = {
            'min': float(base['price'].min()),
            'max': float(base['price'].max()),
        }

        # ---- apply user filters: property_type (comma separated) and price range ----
        results = base

        types_param = request.GET.get('property_type', '').strip()
        if types_param:
            wanted_types = [t for t in types_param.split(',') if t]
            results = results[results['property_type'].astype(str).isin(wanted_types)]

        min_price_param = request.GET.get('min_price', '').strip()
        if min_price_param:
            results = results[results['price'] >= float(min_price_param)]

        max_price_param = request.GET.get('max_price', '').strip()
        if max_price_param:
            results = results[results['price'] <= float(max_price_param)]

        filter_options = {
            'property_types': all_types,
            'price_min': price_bounds['min'],
            'price_max': price_bounds['max'],
        }

        if results.empty:
            return JsonResponse({
                'empty': True,
                'filter_options': filter_options,
                'summary': {
                    'total_listings': 0, 'national_avg_price': 0,
                    'median_price': 0, 'min_price': 0, 'max_price': 0, 'avg_price_per_marla': 0,
                    'priciest_city': '-', 'priciest_price': 0,
                    'cheapest_city': '-', 'cheapest_price': 0,
                    'avg_bedrooms': 0, 'avg_baths': 0,
                    'cities_covered': 0,
                },
                'cities': {c: {'labels': [], 'data': [], 'count': 0} for c in target_cities},
                'city_totals': {'labels': target_cities, 'data': [0, 0, 0, 0], 'counts': [0, 0, 0, 0]},
                'property_types': {'labels': [], 'data': []},
                'purpose_mix': {'labels': [], 'data': []},
                'bedroom_dist': {'labels': [], 'data': []},
                'bathroom_dist': {'labels': [], 'data': []},
                'price_dist': {'labels': [], 'data': []},
                'city_stats': {c: {
                    'count': 0, 'min_price': 0, 'median_price': 0, 'max_price': 0,
                    'avg_bedrooms': 0, 'avg_baths': 0, 'avg_price_per_marla': 0,
                } for c in target_cities},
                'map_points': [],
            })

        # ---- per-city top locations, for the 3D pie charts ----
        cities_payload = {}

        for city in target_cities:

            city_df = results[results['city'] == city]

            if city_df.empty:
                cities_payload[city] = {'labels': [], 'data': [], 'count': 0}
                continue

            loc_prices = (
                city_df.groupby('location')['price']
                .mean()
                .sort_values(ascending=False)
                .head(8)
            )

            cities_payload[city] = {
                'labels': list(loc_prices.index.astype(str)),
                'data': [round(float(v), 2) for v in loc_prices.values],
                'count': int(city_df.shape[0])
            }

        # ---- city-wise average price, for the 3D bar chart ----
        city_totals = results.groupby('city')['price'].mean().reindex(target_cities)
        city_counts = results.groupby('city')['price'].count().reindex(target_cities)

        # ---- sampled lat/long points, for the map ----
        map_points = []

        for city in target_cities:

            city_df = results[results['city'] == city]
            sample = city_df.sample(n=min(250, len(city_df)), random_state=42)

            for _, row in sample.iterrows():
                map_points.append({
                    'lat': float(row['latitude']),
                    'lng': float(row['longitude']),
                    'city': city,
                    'location': str(row['location']),
                    'price': round(float(row['price']), 2),
                    'type': str(row['property_type'])
                })

        # ---- property-type mix, across all four cities ----
        type_counts = (
            results['property_type'].astype(str).value_counts().head(6)
        )

        # ---- purpose mix (for sale / for rent) ----
        purpose_counts = results['purpose'].astype(str).value_counts()

        # ---- bedroom / bathroom distribution (bucketed, capped at "6+") ----
        def bucket_counts(series):
            capped = series.dropna().clip(upper=6)
            counts = capped.value_counts().sort_index()
            labels = [('6+' if int(i) == 6 else str(int(i))) for i in counts.index]
            return labels, [int(v) for v in counts.values]

        bedroom_labels, bedroom_data = bucket_counts(results['bedrooms'])
        bathroom_labels, bathroom_data = bucket_counts(results['baths'])

        # ---- price distribution (bands) ----
        price_band_labels = ['Under 25L', '25L-50L', '50L-1Cr', '1-2Cr', '2-5Cr', '5Cr+']
        price_bucket = pd.cut(
            results['price'],
            bins=[0, 2500000, 5000000, 10000000, 20000000, 50000000, float('inf')],
            labels=price_band_labels,
            right=True
        )
        price_dist_counts = price_bucket.value_counts().reindex(price_band_labels).fillna(0)

        # ---- headline KPIs ----
        valid_totals = city_totals.dropna()
        priciest_city = valid_totals.idxmax()
        cheapest_city = valid_totals.idxmin()

        valid_area_all = results[results['area_marla'] > 0]
        overall_ppm = (
            valid_area_all['price'] / valid_area_all['area_marla']
            if not valid_area_all.empty else pd.Series(dtype=float)
        )

        summary = {
            'total_listings': int(results.shape[0]),
            'national_avg_price': round(float(results['price'].mean()), 2),
            'median_price': round(float(results['price'].median()), 2),
            'min_price': round(float(results['price'].min()), 2),
            'max_price': round(float(results['price'].max()), 2),
            'avg_price_per_marla': round(float(overall_ppm.mean()), 2) if not overall_ppm.empty else 0,
            'priciest_city': priciest_city,
            'priciest_price': round(float(valid_totals.max()), 2),
            'cheapest_city': cheapest_city,
            'cheapest_price': round(float(valid_totals.min()), 2),
            'avg_bedrooms': round(float(results['bedrooms'].mean() or 0), 1),
            'avg_baths': round(float(results['baths'].mean() or 0), 1),
            'cities_covered': int(len(target_cities)),
        }

        # ---- per-city detailed stats table ----
        city_stats = {}

        for city in target_cities:

            city_df = results[results['city'] == city]

            if city_df.empty:
                city_stats[city] = {
                    'count': 0, 'min_price': 0, 'median_price': 0, 'max_price': 0,
                    'avg_bedrooms': 0, 'avg_baths': 0, 'avg_price_per_marla': 0,
                }
                continue

            valid_area = city_df[city_df['area_marla'] > 0]
            price_per_marla = (
                valid_area['price'] / valid_area['area_marla']
                if not valid_area.empty else pd.Series(dtype=float)
            )

            city_stats[city] = {
                'count': int(city_df.shape[0]),
                'min_price': round(float(city_df['price'].min()), 2),
                'median_price': round(float(city_df['price'].median()), 2),
                'max_price': round(float(city_df['price'].max()), 2),
                'avg_bedrooms': round(float(city_df['bedrooms'].mean() or 0), 1),
                'avg_baths': round(float(city_df['baths'].mean() or 0), 1),
                'avg_price_per_marla': round(float(price_per_marla.mean()), 2) if not price_per_marla.empty else 0,
            }

    except Exception as e:
        return HttpResponse(str(e), status=500)

    context = {
        'empty': False,
        'filter_options': filter_options,
        'summary': summary,
        'cities': cities_payload,
        'city_totals': {
            'labels': target_cities,
            'data': [round(float(v), 2) if pd.notna(v) else 0 for v in city_totals.values],
            'counts': [int(v) if pd.notna(v) else 0 for v in city_counts.values],
        },
        'property_types': {
            'labels': list(type_counts.index),
            'data': [int(v) for v in type_counts.values],
        },
        'purpose_mix': {
            'labels': list(purpose_counts.index),
            'data': [int(v) for v in purpose_counts.values],
        },
        'bedroom_dist': {'labels': bedroom_labels, 'data': bedroom_data},
        'bathroom_dist': {'labels': bathroom_labels, 'data': bathroom_data},
        'price_dist': {
            'labels': price_band_labels,
            'data': [int(v) for v in price_dist_counts.values],
        },
        'city_stats': city_stats,
        'map_points': map_points,
    }

    return JsonResponse(context)


#---------------------AI ML MODEL-------------------------
