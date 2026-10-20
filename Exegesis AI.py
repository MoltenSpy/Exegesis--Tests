# --- Updated Weather Function (No Time Included) ---
def get_weather(city_name):
    if not city_name:
        return "Please enter a location.", 0
    try:
        url_j1 = f"https://wttr.in/{city_name}?format=j1"
        resp_j1 = requests.get(url_j1, timeout=5)
        
        if resp_j1.status_code == 200:
            data = resp_j1.json()
            
            # Current Condition & Temps
            condition = data["current_condition"][0]["weatherDesc"][0]["value"]
            temp_c = data["current_condition"][0]["temp_C"]
            temp_f = data["current_condition"][0]["temp_F"]
            
            # Today's High & Low
            today = data["weather"][0]
            min_c = today["mintempC"]
            max_c = today["maxtempC"]
            min_f = today["mintempF"]
            max_f = today["maxtempF"]
            
            # Extract Timezone Offset (in seconds) for accurate local time calculation
            # wttr.in provides timezone offset string, e.g., "+0530" or "-0400"
            tz_str = data["nearest_area"][0]["time_zone"][0]["offsetSecs"]
            tz_offset_seconds = int(tz_str)
            
            weather_text = (
                f"**Condition:** {condition}\n\n"
                f"🌡️ **Current:** {temp_c}°C / {temp_f}°F\n\n"
                f"📉 **Lowest:** {min_c}°C / {min_f}°F\n\n"
                f"📈 **Highest:** {max_c}°C / {max_f}°F"
            )
            return weather_text, tz_offset_seconds
    except Exception:
        pass
    return "Unable to fetch weather data.", 0
