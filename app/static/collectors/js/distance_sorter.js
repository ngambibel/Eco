// distance_sorter.js
class CollectionDistanceSorter {
    constructor(options = {}) {
        this.apiUrl = options.apiUrl || '/api/collections/by-distance/';
        this.updateInterval = options.updateInterval || 30000; // 30 secondes
        this.watchPosition = options.watchPosition !== false;
        self.watchId = null;
        self.currentPosition = null;
        self.collections = [];
        self.filters = {
            maxDistance: options.maxDistance || null,
            hideCompleted: options.hideCompleted || false,
        };
        
        // Callbacks
        self.onUpdate = options.onUpdate || function() {};
        self.onError = options.onError || function() {};
        self.onPositionChange = options.onPositionChange || function() {};
        
        self.init();
    }
    
    init() {
        // Démarrer le suivi de position
        this.startPositionTracking();
        
        // Charger les collectes initiales
        this.loadCollections();
        
        // Mettre à jour périodiquement
        if (this.updateInterval > 0) {
            setInterval(() => this.loadCollections(), this.updateInterval);
        }
    }
    
    startPositionTracking() {
        if (!navigator.geolocation) {
            this.onError({
                type: 'geolocation',
                message: 'La géolocalisation n\'est pas supportée par votre navigateur'
            });
            return;
        }
        
        const options = {
            enableHighAccuracy: true,
            timeout: 10000,
            maximumAge: 0
        };
        
        const success = (position) => {
            const newPosition = {
                lat: position.coords.latitude,
                lon: position.coords.longitude,
                accuracy: position.coords.accuracy,
                timestamp: position.timestamp
            };
            
            // Vérifier si la position a significativement changé
            if (this.hasPositionChanged(newPosition)) {
                self.currentPosition = newPosition;
                this.onPositionChange(newPosition);
                this.loadCollections(); // Recharger avec la nouvelle position
            }
        };
        
        const error = (err) => {
            let message = 'Erreur de géolocalisation';
            switch(err.code) {
                case err.PERMISSION_DENIED:
                    message = 'Permission de géolocalisation refusée';
                    break;
                case err.POSITION_UNAVAILABLE:
                    message = 'Position non disponible';
                    break;
                case err.TIMEOUT:
                    message = 'Délai de géolocalisation dépassé';
                    break;
            }
            
            this.onError({
                type: 'geolocation',
                code: err.code,
                message: message
            });
        };
        
        this.watchId = navigator.geolocation.watchPosition(success, error, options);
    }
    
    hasPositionChanged(newPosition) {
        if (!self.currentPosition) return true;
        
        // Considérer un changement significatif si plus de 50 mètres
        const distance = this.calculateDistance(
            self.currentPosition.lat, self.currentPosition.lon,
            newPosition.lat, newPosition.lon
        );
        
        return distance > 0.05; // 50 mètres
    }
    
    calculateDistance(lat1, lon1, lat2, lon2) {
        const R = 6371; // Rayon de la Terre en km
        const dLat = this.toRad(lat2 - lat1);
        const dLon = this.toRad(lon2 - lon1);
        const a = 
            Math.sin(dLat/2) * Math.sin(dLat/2) +
            Math.cos(this.toRad(lat1)) * Math.cos(this.toRad(lat2)) * 
            Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        return R * c;
    }
    
    toRad(degrees) {
        return degrees * Math.PI / 180;
    }
    
    async loadCollections() {
        if (!self.currentPosition) {
            console.log('Position non disponible, chargement différé...');
            return;
        }
        
        // Construire l'URL avec les paramètres
        const url = new URL(this.apiUrl, window.location.origin);
        url.searchParams.append('lat', self.currentPosition.lat);
        url.searchParams.append('lon', self.currentPosition.lon);
        
        // Ajouter la date si présente dans l'URL
        const urlParams = new URLSearchParams(window.location.search);
        const date = urlParams.get('date');
        if (date) {
            url.searchParams.append('date', date);
        }
        
        try {
            const response = await fetch(url, {
                method: 'GET',
                headers: {
                    'X-Requested-With': 'XMLHttpRequest',
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                self.collections = data.collections;
                this.applyFilters();
                this.onUpdate({
                    collections: self.collections,
                    stats: data.stats,
                    userPosition: data.user_position,
                    raw: data
                });
            } else {
                this.onError({
                    type: 'api',
                    message: data.error || 'Erreur lors du chargement des collectes'
                });
            }
        } catch (error) {
            this.onError({
                type: 'network',
                message: error.message || 'Erreur réseau'
            });
        }
    }
    
    setFilter(key, value) {
        this.filters[key] = value;
        this.applyFilters();
    }
    
    applyFilters() {
        let filtered = [...self.collections];
        
        // Filtre par distance maximale
        if (this.filters.maxDistance) {
            filtered = filtered.filter(c => c.distance_km <= this.filters.maxDistance);
        }
        
        // Filtre pour cacher les collectes terminées
        if (this.filters.hideCompleted) {
            filtered = filtered.filter(c => c.status !== 'completed');
        }
        
        // Mettre à jour l'affichage via le callback
        this.onUpdate({
            collections: filtered,
            allCollections: self.collections,
            filters: this.filters
        });
    }
    
    stop() {
        if (this.watchId) {
            navigator.geolocation.clearWatch(this.watchId);
        }
    }
    
    getNearestCollection() {
        if (!self.collections || self.collections.length === 0) return null;
        return self.collections[0];
    }
    
    getFarthestCollection() {
        if (!self.collections || self.collections.length === 0) return null;
        return self.collections[self.collections.length - 1];
    }
    
    getCollectionsByZone(zoneName) {
        return self.collections.filter(c => c.zone_name === zoneName);
    }
    
    getTotalDistance() {
        if (!self.collections || self.collections.length < 2) return 0;
        
        let totalDistance = 0;
        let previous = self.collections[0];
        
        for (let i = 1; i < self.collections.length; i++) {
            const current = self.collections[i];
            totalDistance += this.calculateDistance(
                previous.address.latitude, previous.address.longitude,
                current.address.latitude, current.address.longitude
            );
            previous = current;
        }
        
        return totalDistance;
    }
    
    estimateTotalTime() {
        if (!self.collections || self.collections.length === 0) return 0;
        
        // Estimation: 5 minutes par collecte + temps de trajet
        const timePerCollection = 5 * 60; // 5 minutes en secondes
        let totalTime = self.collections.length * timePerCollection;
        
        // Ajouter le temps de trajet entre les collectes
        if (self.collections.length > 1) {
            for (let i = 0; i < self.collections.length - 1; i++) {
                const current = self.collections[i];
                const next = self.collections[i + 1];
                
                // Estimation grossière: 30 secondes par km
                const travelTime = next.distance_km * 30 * 60; // en secondes
                totalTime += travelTime;
            }
        }
        
        return totalTime;
    }
}

// Export pour utilisation
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CollectionDistanceSorter;
}