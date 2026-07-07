FROM python:3.12-slim

WORKDIR /app

# Tizim paketlarini o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Talablar faylini yuklash va o'rnatish
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Loyihani nusxalash
COPY . .

# Ishga tushirish skriptiga ruxsat berish
RUN chmod +x start.sh

# Portni ochish (Server uchun)
EXPOSE 8000

# Ishga tushirish buyrug'i
CMD ["./start.sh"]
