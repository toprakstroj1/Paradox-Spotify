# Paradox-Spotify
Spotify için Flet ile geliştirilmiş, çoklu sanatçı ve Buzdağı (Iceberg) modu destekli, akıllı toplu playlist oluşturma aracı.
# PARADOX Flet: Spotify Masterpiece Playlist Generator 🎧

![Python Versiyonu](https://img.shields.io/badge/Python-3.10%2B-blue)
![Kullanıcı Arayüzü](https://img.shields.io/badge/UI%20Framework-Flet-brightgreen)
![Spotify Kütüphanesi](https://img.shields.io/badge/API%20Wrapper-Spotipy-red)

Python'da modern **Flet** framework'ü ve **Spotipy** kütüphanesi kullanılarak geliştirilmiş, sanatçıların diskografisinden akıllıca seçilmiş parçalarla (özellikle benzersiz **Buzdağı Modu** ile) toplu ve kişiselleştirilmiş çalma listeleri oluşturmaya yarayan bir masaüstü uygulamasıdır.

## ✨ Temel Özellikler

Bu uygulama, standart playlist oluşturma araçlarının ötesine geçer:

* **🧊 Buzdağı (Iceberg) Modu:** Seçilen her sanatçıdan, hayranlık seviyesine göre katmanlı parça seçimi yapar (Max 40 Şarkı):
    * **Zirve (Top 10):** Sanatçının en popüler 10 parçası.
    * **Orta Katman (10 Popüler):** Hayranların en çok bildiği, popülerlik sırasına göre sonraki 10 parça.
    * **Derin Kesim (20 Gerçek Hayran):** En düşük popülerliğe sahip, gerçek hayranların bildiği 20 parça.
* **Çoklu Sanatçı Desteği:** Tek bir playliste sınırsız sayıda sanatçının parçalarını toplu ekleme.
* **Kapsamlı Filtreleme:** Albüm, Single, Compilation tiplerine göre filtreleme ve 60 saniyeden kısa parçaları hariç tutma seçeneği.
* **Playlist Yönetimi:** Yeni oluşturma, varolanın üzerine yazma (`OVERWRITE`) veya mevcut playliste ekleme (`APPEND`) seçenekleri.
* **Otomatik Kapak:** Playlist oluşturulurken, seçilen son sanatçının görselini kapak resmi olarak yükler.
* **Modern UI:** Flet sayesinde platformlar arası uyumlu, hızlı ve modern bir kullanıcı arayüzü.

## ⚙️ Kurulum ve Çalıştırma

### 1. Ön Gereksinimler

* Python 3.10 veya üzeri
* Spotify Developer Hesabı

### 2. Spotify API Ayarları

1.  **[Spotify Developer Dashboard](https://developer.spotify.com/dashboard/applications)**'a gidin ve yeni bir uygulama (App) oluşturun.
2.  Uygulamanızın **`Client ID`** ve **`Client Secret`** değerlerini not alın.
3.  Uygulamanızın ayarlarındaki (**`Edit Settings`**) **`Redirect URIs`** kısmına aşağıdaki adresi ekleyin:

    ```
    [http://170.0.0.1:8080/callback](http://170.0.0.1:8080/callback)
    ```

    > **Not:** Kodda kullanılan `REDIRECT_URI` budur. Güvenliğiniz için bu adresi doğru girdiğinizden emin olun.

4.  `paradox_spotify.py` dosyasını açın ve dosyanın başındaki `CLIENT_ID` ve `CLIENT_SECRET` alanlarını kendi değerlerinizle güncelleyin:

    ```python
    CLIENT_ID: str = "SPOTIFY_CLIENT_ID_BURAYA"
    CLIENT_SECRET: str = "SPOTIFY_CLIENT_SECRET_BURAYA"
    ```

### 3. Uygulamayı Kurma

Projeyi klonlayın ve gerekli Python kütüphanelerini kurun:

```bash
# Depoyu klonlayın
git clone <REPO_URL>
cd <REPO_ADI>

# Bağımlılıkları yükleyin
pip install flet requests pillow spotipy
