from django import template

register = template.Library()

@register.filter
def filter_factures(factures, abonnement):
    """Filtre les factures par abonnement"""
    return [facture for facture in factures if facture.demande == abonnement]