from typing import Tuple
from rapidfuzz import fuzz
from src.data.base_provider import RawListing
from src.utils.config import AgentParameters
import structlog

logger = structlog.get_logger()

class FilterEngine:
    def __init__(self):
        pass

    def evaluate(self, listing: RawListing, params: AgentParameters) -> Tuple[bool, float]:
        """
        Evaluates a listing against agent parameters.
        Returns (is_match, score).
        """
        score = 0.0
        
        # 0. Multi-Vehicle Criteria Match
        if params.vehicles:
            vehicle_match = False
            for v in params.vehicles:
                m_match = False
                if listing.make and fuzz.partial_ratio(v.make.lower(), listing.make.lower()) > 90:
                    m_match = True
                elif not listing.make and fuzz.partial_ratio(v.make.lower(), listing.title.lower()) > 90:
                    m_match = True
                
                if not m_match: continue
                
                mod_match = False
                if listing.model and fuzz.partial_ratio(v.model.lower(), listing.model.lower()) > 85:
                    mod_match = True
                elif not listing.model and fuzz.partial_ratio(v.model.lower(), listing.title.lower()) > 85:
                    mod_match = True
                
                if not mod_match: continue
                
                # Year check for this specific vehicle
                if listing.year:
                    if v.year_min and listing.year < v.year_min: continue
                    if v.year_max and listing.year > v.year_max: continue
                
                vehicle_match = True
                score += 30.0 # Combined make/model score
                break
            
            if not vehicle_match:
                return False, 0.0
        else:
            # 1. Make Match (Fuzzy)
            if params.makes:
                make_match = False
                for make in params.makes:
                    if listing.make and fuzz.partial_ratio(make.lower(), listing.make.lower()) > 90:
                        make_match = True
                        break
                    # Fallback to title check if make is not explicitly parsed
                    if not listing.make and fuzz.partial_ratio(make.lower(), listing.title.lower()) > 90:
                        make_match = True
                        break
                if not make_match:
                    return False, 0.0
                score += 10.0

            # 2. Model Match (Fuzzy)
            if params.models:
                model_match = False
                for model in params.models:
                    if listing.model and fuzz.partial_ratio(model.lower(), listing.model.lower()) > 85:
                        model_match = True
                        break
                    if not listing.model and fuzz.partial_ratio(model.lower(), listing.title.lower()) > 85:
                        model_match = True
                        break
                if not model_match:
                    return False, 0.0
                score += 20.0

            # 3. Year Range
            if listing.year:
                if params.year_min and listing.year < params.year_min:
                    return False, 0.0
                if params.year_max and listing.year > params.year_max:
                    return False, 0.0
                score += 5.0

        # 4. Price Range
        if listing.price:
            if params.price_max and listing.price > params.price_max:
                return False, 0.0
            score += 10.0

        # 5. Mileage Range
        if listing.mileage:
            if params.mileage_max and listing.mileage > params.mileage_max:
                return False, 0.0
            score += 5.0

        # 6. Exclude Keywords
        if params.exclude_keywords:
            for kw in params.exclude_keywords:
                if kw.lower() in listing.title.lower():
                    return False, 0.0

        # 7. Features (Any)
        if params.features_any:
            feature_found = False
            for feature in params.features_any:
                if feature.lower() in listing.title.lower():
                    feature_found = True
                    score += 5.0
            # We don't necessarily fail if features_any isn't met, 
            # unless the user intended it as a hard filter. 
            # For now, we treat it as a score booster.

        return True, score
