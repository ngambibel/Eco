from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import *

# Admin pour City
@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('city', 'country', 'region')
    list_filter = ('country', 'region')
    search_fields = ('city', 'country', 'region')
    ordering = ('city',)

# Admin personnalisé pour CustomUser
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'user_type', 'city', 'phone', 'is_verified', 'date_joined')
    list_filter = ('user_type', 'is_verified', 'date_joined', 'city')
    search_fields = ('username', 'email', 'phone')
    ordering = ('-date_joined',)
    
    fieldsets = UserAdmin.fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('user_type', 'phone', 'city', 'is_verified')
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Informations supplémentaires', {
            'fields': ('user_type', 'phone', 'city', 'is_verified')
        }),
    )

# Admin pour Address
class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    fields = ('title', 'street', 'city', 'postal_code', 'country', 'is_primary')
    readonly_fields = ('created_at',)

@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ('user', 'title', 'city', 'postal_code', 'country', 'is_primary', 'created_at')
    list_filter = ('country', 'city', 'is_primary', 'created_at')
    search_fields = ('user__username', 'title', 'street', 'city', 'postal_code')
    readonly_fields = ('id', 'created_at')
    ordering = ('-created_at',)

# Admin pour SubscriptionPlan
@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'plan_type', 'frequency', 'price', 'max_collections_per_week', 'is_active')
    list_filter = ('plan_type', 'frequency', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at',)
    list_editable = ('is_active', 'price')

# Admin pour CollectionDay
@admin.register(CollectionDay)
class CollectionDayAdmin(admin.ModelAdmin):
    list_display = ('name', 'order')
    list_editable = ('order',)
    ordering = ('order',)

# Inline pour SubscriptionDay
class SubscriptionDayInline(admin.TabularInline):
    model = SubscriptionDay
    extra = 0
    fields = ('day', 'time_slot', 'is_active')
    min_num = 1

# Admin pour Subscription
class SubscriptionInline(admin.TabularInline):
    model = Subscription
    extra = 0
    fields = ('plan', 'status', 'start_date', 'end_date')
    readonly_fields = ('created_at',)

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('user', 'plan', 'status', 'start_date', 'end_date', 'created_at')
    list_filter = ('status', 'plan', 'start_date', 'created_at')
    search_fields = ('user__phone', 'plan__name', 'address__title')
    readonly_fields = ('id', 'created_at', 'updated_at')
    inlines = [SubscriptionDayInline]
    ordering = ('-created_at',)

# Admin pour SubscriptionDay
@admin.register(SubscriptionDay)
class SubscriptionDayAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'day', 'time_slot', 'is_active')
    list_filter = ('day', 'is_active', 'time_slot')
    search_fields = ('subscription__user__username', 'day__name')
    list_editable = ('time_slot', 'is_active')

# Admin pour CollectionRequest
@admin.register(CollectionRequest)
class CollectionRequestAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'scheduled_date', 'scheduled_time', 'status', 'collector', 'actual_collection_time')
    list_filter = ('status', 'scheduled_date', 'collector')
    search_fields = ('subscription__user__username', 'collector__username', 'notes')
    readonly_fields = ('id', 'created_at', 'updated_at')
    ordering = ('-scheduled_date', '-scheduled_time')
    date_hierarchy = 'scheduled_date'

# Admin pour Payment
@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'amount', 'status', 'payment_date', 'due_date', 'payment_method')
    list_filter = ('status', 'payment_date', 'due_date', 'payment_method')
    search_fields = ('subscription__user__username', 'transaction_id')
    readonly_fields = ('created_at',)
    ordering = ('-payment_date',)
    date_hierarchy = 'payment_date'

# Admin pour AnnonceCarousel
@admin.register(AnnonceCarousel)
class AnnonceCarouselAdmin(admin.ModelAdmin):
    list_display = ('titre', 'date_debut', 'date_fin', 'actif', 'ordre', 'est_actif')
    list_filter = ('actif', 'date_debut', 'date_fin')
    search_fields = ('titre', 'description')
    readonly_fields = ('date_creation',)
    list_editable = ('actif', 'ordre')
    ordering = ('ordre', '-date_creation')
    date_hierarchy = 'date_creation'

# Admin pour CollectionSchedule
@admin.register(CollectionSchedule)
class CollectionScheduleAdmin(admin.ModelAdmin):
    list_display = ('subscription', 'scheduled_date', 'scheduled_day', 'scheduled_time', 'status', 'completed_at')
    list_filter = ('status', 'scheduled_date', 'scheduled_day')
    search_fields = ('subscription__user__username', 'collector_notes', 'customer_notes')
    readonly_fields = ('created_at',)
    ordering = ('-scheduled_date', '-scheduled_time')
    date_hierarchy = 'scheduled_date'

# Enregistrement des modèles
admin.site.register(CustomUser, CustomUserAdmin)


admin.site.register(Zone)
admin.site.register(Tricycle)
admin.site.register(ProgrammeTricycle)

admin.site.register(DemandeReabonnement)
admin.site.register(Facture)
admin.site.register(Abonnement)
admin.site.register(RevenueRecord)
admin.site.register(RevenueSummary)






