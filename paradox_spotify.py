import base64
import json
import urllib.parse
import webbrowser
import sys
import threading
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set, Any
from io import BytesIO
from datetime import datetime, timedelta
import asyncio
import time

import requests
from PIL import Image
import flet as ft

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy import SpotifyException

CLIENT_ID: str = "SPOTIFY_CLIENT_ID_BURAYA"
CLIENT_SECRET: str = "SPOTIFY_CLIENT_SECRET_BURAYA"

REDIRECT_URI: str = "http://127.0.0.1:8080/callback"
SETTINGS_STORE: Path = Path.home() / ".paradox_flet_spotipy_cache"

SCOPES: str = "playlist-modify-private playlist-modify-public user-read-private ugc-image-upload user-read-email"

class MainApp:
    
    def __init__(self, page: ft.Page):
        self.page = page
        self.page.title = "PARADOX Flet: Spotify Masterpiece (Spotipy)"
        self.page.theme_mode = ft.ThemeMode.DARK
        self.page.vertical_alignment = ft.MainAxisAlignment.START
        
        self.sp: Optional[spotipy.Spotify] = None
        self.client_id: str = CLIENT_ID
        self.client_secret: str = CLIENT_SECRET
        self.current_user_id: Optional[str] = None
        
        self.current_artist_id: Optional[str] = None
        self.current_artist_image_url: Optional[str] = None
        self.current_playlist_id: Optional[str] = None
        self.selected_artists: Dict[str, str] = {}
        self.current_playlist_url: Optional[str] = None
        self.is_connected: bool = False

        self.log_text = ft.Text("Hazır. Kimlik bilgilerini girin ve bağlanın.", color=ft.Colors.GREY_400)
        self.status_text = ft.Text("Bağlantı Bekleniyor", color=ft.Colors.YELLOW_ACCENT_400, weight=ft.FontWeight.BOLD)
        self.log_container = ft.Column(scroll=ft.ScrollMode.ADAPTIVE, height=150)
        
        self.user_profile_image = ft.Container(
            content=ft.Icon(ft.Icons.PERSON, size=50, color=ft.Colors.GREY_700),
            width=60, height=60, border_radius=30, bgcolor=ft.Colors.BLACK38, alignment=ft.alignment.center
        )
        self.user_profile_name = ft.Text("Bağlanmadı", size=16, weight=ft.FontWeight.BOLD)
        self.user_profile_id = ft.Text("Lütfen Spotify'a Bağlanın.")
        self.user_profile_link = ft.TextButton("Profil Linki", url="", visible=False, style=ft.ButtonStyle(padding=0))
        
        self.progress_bar = ft.ProgressBar(width=400, value=0)
        self.stats_text_total_album = ft.Text("Toplam Albüm: 0", color=ft.Colors.CYAN_ACCENT_100)
        self.stats_text_total_track = ft.Text("Toplanan Parça: 0", color=ft.Colors.LIME_ACCENT_400)
        self.stats_text_added_track = ft.Text("Eklenen Parça: 0", color=ft.Colors.GREEN_ACCENT_400)
        
        self.flow_stats_container = ft.Column(
            [self.stats_text_total_album, self.stats_text_total_track, self.stats_text_added_track, self.progress_bar],
            spacing=10, visible=True, alignment=ft.MainAxisAlignment.START
        )
        
        self.flow_stats_wrapper = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Akış İlerlemesi", size=18, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=self.flow_stats_container,
                        padding=15,
                        bgcolor=ft.Colors.BLACK38,
                        border_radius=10,
                        expand=True,
                        alignment=ft.alignment.top_left
                    )
                ],
                expand=True
            ),
            expand=1,
            visible=False,
            padding=ft.padding.only(right=10)
        )
        
        self.playlist_cover = ft.Container(
            content=ft.Icon(ft.Icons.LIBRARY_MUSIC, size=60, color=ft.Colors.GREEN_ACCENT_700),
            width=100, height=100, border_radius=5, bgcolor=ft.Colors.BLACK38, alignment=ft.alignment.center
        )
        self.playlist_name_label_preview = ft.Text("Playlist Önizlemesi Yok", size=16, weight=ft.FontWeight.BOLD)
        self.playlist_track_count = ft.Text("Parça Sayısı: -")
        self.playlist_open_button = ft.ElevatedButton("Playlist'i Aç", on_click=self._open_playlist_link, visible=False)
        self.playlist_preview_container = ft.Container(
            content=ft.Row([self.playlist_cover, ft.Column(
                [self.playlist_name_label_preview, self.playlist_track_count, self.playlist_open_button],
                spacing=5, horizontal_alignment=ft.CrossAxisAlignment.START
            )], spacing=20, vertical_alignment=ft.CrossAxisAlignment.START),
            padding=20,
            bgcolor=ft.Colors.BLACK26,
            border_radius=10,
            visible=False
        )

        self.client_id_entry = ft.TextField(
            label="Spotify Client ID", 
            width=350, 
            value=self.client_id,
            on_change=self._update_credentials
        )
        self.client_secret_entry = ft.TextField(
            label="Spotify Client Secret", 
            width=350, 
            value=self.client_secret,
            on_change=self._update_credentials,
            password=True, 
            can_reveal_password=True
        )
        
        self.artist_search_entry = ft.TextField(label="Sanatçı Adı (Örn: Daft Punk)", width=300, on_submit=self._quick_search_artist_click)
        self.artist_search_button = ft.IconButton(
            icon=ft.Icons.SEARCH, 
            tooltip="Sanatçıyı Ara ve Seçili Listeye Ekle", 
            on_click=self._quick_search_artist_click,
            icon_color=ft.Colors.GREEN_ACCENT_700
        )
        
        self.selected_artists_column = ft.Column(
            [ft.Text("Seçili Sanatçılar (0)", weight=ft.FontWeight.BOLD)],
            scroll=ft.ScrollMode.ADAPTIVE, height=150, spacing=5,
            horizontal_alignment=ft.CrossAxisAlignment.START
        )

        self.playlist_name_entry = ft.TextField(label="Oluşturulacak Playlist Adı", width=350)
        self.existing_playlist_entry = ft.TextField(label="Mevcut Playlist ID/URL (Opsiyonel)", width=350)
        
        self.playlist_mode_combo = ft.Dropdown(label="Playlist Modu", value="NEW", options=[
            ft.dropdown.Option("NEW", "Yeni Oluştur"),
            ft.dropdown.Option("OVERWRITE", "Varolanı Silip Yeniden Yaz"),
            ft.dropdown.Option("APPEND", "Varolana Ekle"),
        ], width=350)
        
        self.sort_combo = ft.Dropdown(label="Sıralama Tipi", value="TRACK", options=[
            ft.dropdown.Option("TRACK", "Albümdeki Sırasına Göre"),
            ft.dropdown.Option("POPULARITY", "Popülerliğe Göre (Azalan)"),
            ft.dropdown.Option("TOP_TRACKS", "Spotify Top 10 Tracks (Önce)"),
            # YENİ BUZDAĞI SEÇENEĞİ
            ft.dropdown.Option("ICEBERG", "Buzdağı (Max 40 Şarkı, Katmanlı)")
        ], width=350)

        self.album_check = ft.Checkbox(label="Albums", value=True)
        self.single_check = ft.Checkbox(label="Singles", value=True)
        self.compilation_check = ft.Checkbox(label="Compilations", value=False)
        self.exclude_short_check = ft.Checkbox(label="Exclude tracks < 60s", value=True)
        self.public_check = ft.Checkbox(label="Public Playlist", value=True)
        
        self.connect_button = ft.ElevatedButton(text="🔗 Spotify'a Bağlan", on_click=self._connect_to_spotify_click, width=350)
        
        self.start_flow_button = ft.ElevatedButton(
            text="▶ Akışı Başlat (Playlist Oluştur/Güncelle)", 
            on_click=self._start_flow_click, 
            width=350, 
            disabled=True, 
            style=ft.ButtonStyle(bgcolor={ft.ControlState.DEFAULT: ft.Colors.BLUE_700})
        )
        
        self.check_button = ft.OutlinedButton(text="ℹ Playlist Kontrol", on_click=self._check_playlist_click, width=350)
        
        self.delete_playlist_button = ft.OutlinedButton(
            text="❌ Playlist Sil (Unfollow)", 
            on_click=self._delete_playlist_click, 
            width=350, 
            disabled=True, 
            style=ft.ButtonStyle(color={ft.ControlState.DEFAULT: ft.Colors.RED_ACCENT_700})
        )
        
        self.artist_image_control = ft.Container(
            content=ft.Icon(ft.Icons.IMAGE, size=100, color=ft.Colors.GREY_700),
            width=250, height=250, border_radius=10, bgcolor=ft.Colors.BLACK38, alignment=ft.alignment.center
        )
        self.artist_name_label = ft.Text("Sanatçı Keşfetme (Son Aranan)", size=18, weight=ft.FontWeight.BOLD)
        self.artist_followers_label = ft.Text("")
        
        self._init_layout()
        self.page.run_thread(self._check_initial_connection)


    def _init_layout(self):
        
        input_controls_column = ft.Column(
            [
                ft.Text("Spotify API Bağlantısı", size=18, weight=ft.FontWeight.BOLD),
                self.client_id_entry,
                self.client_secret_entry, 
                self.connect_button,
                ft.Divider(height=20, color=ft.Colors.WHITE30),
                
                ft.Text("Sanatçı ve Playlist Ayarları", size=18, weight=ft.FontWeight.BOLD),
                
                ft.Row([self.artist_search_entry, self.artist_search_button], alignment=ft.MainAxisAlignment.START, spacing=5),
                
                ft.Container(
                    content=self.selected_artists_column,
                    bgcolor=ft.Colors.BLACK38,
                    padding=10,
                    border_radius=5,
                    width=350,
                    height=150
                ),
                
                self.playlist_name_entry,
                self.existing_playlist_entry,
                self.playlist_mode_combo,
                self.sort_combo,
                ft.Row([self.album_check, self.single_check, self.compilation_check]),
                ft.Row([self.exclude_short_check, self.public_check]), 
                ft.Divider(height=20, color=ft.Colors.WHITE30),
                self.start_flow_button,
                self.check_button,
                self.delete_playlist_button,
            ],
            spacing=15,
            scroll=ft.ScrollMode.ADAPTIVE
        )
        
        input_controls = ft.Container(
            content=input_controls_column,
            padding=ft.padding.all(20),
            border_radius=10,
            bgcolor=ft.Colors.BLACK26,
            expand=True # Sol panelin dikey olarak genişlemesini sağlar
        )
        
        user_info_control = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Bağlı Kullanıcı", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.LIGHT_BLUE_ACCENT_100),
                    ft.Row(
                        [
                            self.user_profile_image,
                            ft.Column([
                                self.user_profile_name,
                                self.user_profile_id,
                                self.user_profile_link,
                            ], spacing=5, alignment=ft.MainAxisAlignment.START)
                        ],
                        spacing=15,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER
                    ),
                ],
                spacing=15
            ),
            padding=20,
            bgcolor=ft.Colors.BLACK26,
            border_radius=10,
        )

        artist_discovery_control = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Sanatçı Keşfetme ve Durum", size=18, weight=ft.FontWeight.BOLD),
                    ft.Row(
                        [
                            self.artist_image_control,
                            ft.Column([
                                self.artist_name_label,
                                self.artist_followers_label,
                                ft.Text("Status:", weight=ft.FontWeight.BOLD),
                                self.status_text,
                            ], spacing=10, alignment=ft.MainAxisAlignment.START)
                        ],
                        spacing=20
                    ),
                ],
                spacing=15
            ),
            padding=20,
            bgcolor=ft.Colors.BLACK26,
            border_radius=10,
        )
        
        discovery_log_controls = ft.Column(
            [
                user_info_control,
                ft.Divider(height=10, color=ft.Colors.WHITE30),
                
                artist_discovery_control,
                
                ft.Divider(height=10, color=ft.Colors.WHITE30),

                self.playlist_preview_container,
                
                ft.Divider(height=10, color=ft.Colors.WHITE30),
                
                ft.Row([
                    
                    self.flow_stats_wrapper, 

                    ft.Column(
                        [
                            ft.Text("İşlem Logları", size=18, weight=ft.FontWeight.BOLD),
                            ft.Container(
                                content=self.log_container,
                                border_radius=10,
                                bgcolor=ft.Colors.BLACK87,
                                padding=ft.padding.all(10),
                                expand=True
                            )
                        ],
                        expand=2 
                    )
                ], expand=True, alignment=ft.CrossAxisAlignment.START)
            ],
            expand=True
        )

        self.page.add(
            ft.Row(
                [
                    ft.Container(input_controls, expand=1),
                    ft.Container(discovery_log_controls, expand=2),
                ],
                expand=True,
                spacing=20
            )
        )
        
        self.log_container.controls.append(self.log_text)
        self.page.update()

    # ... (Diğer helper fonksiyonlar burada devam eder)

    def playlist_id_from_input(self, input_str: str) -> Optional[str]:
        if "spotify:playlist:" in input_str:
            return input_str.split("spotify:playlist:")[-1].split("?")[0].strip()
        if "/playlist/" in input_str:
            return input_str.split("/playlist/")[-1].split("?")[0].strip()
        return input_str.strip() if input_str else None
    
    def _log(self, message: str, type: str = "info"):
        color_map = {
            "info": ft.Colors.GREY_400, "succ": ft.Colors.LIGHT_GREEN_ACCENT_400,
            "error": ft.Colors.RED_ACCENT_700, "warn": ft.Colors.YELLOW_ACCENT_400,
            "cyan": ft.Colors.CYAN_ACCENT_400
        }
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        log_entry = ft.Text(f"{timestamp} {message}", color=color_map.get(type, ft.Colors.GREY_400), size=12)
        
        def update_log_ui():
            self.log_container.controls.append(log_entry)
            self.log_container.scroll_to(offset=-1) 
            self.page.update()

        if threading.current_thread() == threading.main_thread():
             update_log_ui()
        else:
             self.page.run_thread(update_log_ui) 


    def _update_status(self, message: str, type: str = "info"):
        color_map = {
            "info": ft.Colors.LIGHT_BLUE_ACCENT_100, "err": ft.Colors.RED_ACCENT_700,
            "succ": ft.Colors.LIGHT_GREEN_ACCENT_400,
        }
        def update_status_ui():
            self.status_text.value = message
            self.status_text.color = color_map.get(type, ft.Colors.LIGHT_BLUE_ACCENT_100)
            self.page.update()
            
        if threading.current_thread() == threading.main_thread():
             update_status_ui()
        else:
             self.page.run_thread(update_status_ui)
            
    def _update_credentials(self, e: ft.ControlEvent):
        self.client_id = self.client_id_entry.value
        self.client_secret = self.client_secret_entry.value
        self.page.update()

    def _update_user_profile(self, user_data: Optional[dict]):
        if user_data:
            name = user_data.get('display_name', 'Spotify User')
            user_id = user_data.get('id', 'N/A')
            url = user_data.get('external_urls', {}).get('spotify')
            image_url = user_data.get('images', [{}])
            image_url = image_url[0].get('url') if image_url else None

            self.user_profile_name.value = name
            self.user_profile_id.value = f"ID: {user_id}"
            self.current_user_id = user_id
            
            if url:
                self.user_profile_link.url = url
                self.user_profile_link.visible = True
            else:
                self.user_profile_link.visible = False

            if image_url:
                self.user_profile_image.content = ft.Image(src=image_url, fit=ft.ImageFit.COVER)
                self.user_profile_image.border_radius = 30
            else:
                self.user_profile_image.content = ft.Icon(ft.Icons.PERSON, size=50, color=ft.Colors.GREEN_ACCENT_400)
                self.user_profile_image.border_radius = 5
        
        self.page.run_thread(self.page.update)
    
    def _update_flow_stats(self, step: str, current: int = 0, total: int = 1, added: int = 0):
        def update_ui():
            self.playlist_preview_container.visible = False
            self.flow_stats_wrapper.visible = True 
            
            self.progress_bar.value = current / total if total > 0 else 0
            
            controls = [self.stats_text_total_album, self.stats_text_total_track, self.stats_text_added_track, self.progress_bar]

            if step == "ALBUM_COUNT":
                self.stats_text_total_album.value = f"Toplam Albüm: {total}"
                controls.insert(0, ft.Text(f"Albüm Taranıyor: {current}/{total}", color=ft.Colors.YELLOW_ACCENT_400))
            elif step == "TRACK_COUNT":
                self.stats_text_total_track.value = f"Toplanan Parça: {current}"
            elif step == "ADDING_TRACKS":
                self.stats_text_added_track.value = f"Eklenen Parça: {added}/{total}"
                controls.insert(0, ft.Text(f"Parçalar Ekleniyor: {added}/{total}", color=ft.Colors.GREEN_ACCENT_400))
            
            self.flow_stats_container.controls = controls
            self.page.update()
            
        self.page.run_thread(update_ui)
        
    def _update_playlist_preview(self, playlist_data: Optional[dict], cover_url: Optional[str] = None):
        def update_ui():
            if playlist_data:
                name = playlist_data.get('name', 'Bilinmiyor')
                track_count = playlist_data.get('tracks', {}).get('total', 0)
                url = playlist_data.get('external_urls', {}).get('spotify')

                self.playlist_name_label_preview.value = name
                self.playlist_track_count.value = f"Parça Sayısı: {track_count}"
                self.playlist_preview_container.visible = True
                
                if url:
                    self.current_playlist_url = url
                    self.playlist_open_button.visible = True
                else:
                    self.playlist_open_button.visible = False
                    
                final_cover_url = cover_url or playlist_data.get('images', [{}])[0].get('url')

                if final_cover_url:
                    self.playlist_cover.content = ft.Image(src=final_cover_url, fit=ft.ImageFit.COVER)
                else:
                    self.playlist_cover.content = ft.Icon(ft.Icons.LIBRARY_MUSIC, size=60, color=ft.Colors.GREEN_ACCENT_700)
            else:
                self.playlist_preview_container.visible = False
                
            self.flow_stats_wrapper.visible = False
            self.page.update()
            
        self.page.run_thread(update_ui)
        
    def _open_playlist_link(self, e):
        if self.current_playlist_url:
            webbrowser.open(self.current_playlist_url)

    def _update_selected_artists_ui(self):
        self.selected_artists_column.controls.clear()
        self.selected_artists_column.controls.append(
            ft.Text(f"Seçili Sanatçılar ({len(self.selected_artists)})", weight=ft.FontWeight.BOLD)
        )
        
        for artist_id, name in self.selected_artists.items():
            self.selected_artists_column.controls.append(
                ft.Row(
                    [
                        ft.Text(name, size=12, color=ft.Colors.GREEN_ACCENT_400),
                        ft.IconButton(
                            ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_500, icon_size=16,
                            tooltip=f"{name}'ı Kaldır",
                            on_click=lambda e, a_id=artist_id: self._remove_selected_artist(a_id)
                        )
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                )
            )
        self.page.run_thread(self.page.update) 
        self.page.run_thread(lambda: self.set_ui_enabled(True))
        
    def _remove_selected_artist(self, artist_id: str):
        if artist_id in self.selected_artists:
            name = self.selected_artists.pop(artist_id)
            self._log(f"Sanatçı listeden kaldırıldı: {name}", "warn")
            self._update_selected_artists_ui()
            
    def _add_selected_artist(self, artist_id: str, name: str):
        if artist_id not in self.selected_artists:
            self.selected_artists[artist_id] = name
            self._log(f"Sanatçı listeye eklendi: {name}", "succ")
            self._update_selected_artists_ui()
        else:
            self._log(f"UYARI: Sanatçı '{name}' zaten listede.", "warn")
            self.page.update()

    def _update_artist_info(self, artist_data):
        if artist_data:
            name = artist_data.get('name', 'Bilinmiyor')
            followers = artist_data.get('followers', {}).get('total', 0)
            image_url = artist_data.get('images', [{}])[0].get('url')
            
            self.artist_name_label.value = f"Son Aranan: {name}"
            self.artist_followers_label.value = f"Takipçi: {followers:,}"
            
            if image_url:
                self.current_artist_image_url = image_url
                self.artist_image_control.content = ft.Image(src=image_url, fit=ft.ImageFit.COVER)
            else:
                self.current_artist_image_url = None
                self.artist_image_control.content = ft.Icon(ft.Icons.IMAGE, size=100, color=ft.Colors.ORANGE_A700)
        else:
            self.artist_name_label.value = "Sanatçı Keşfetme (Son Aranan)"
            self.artist_followers_label.value = "Lütfen önce arama yapın."
            self.current_artist_image_url = None
            self.artist_image_control.content = ft.Icon(ft.Icons.IMAGE, size=100, color=ft.Colors.GREY_700)
            
        self.page.run_thread(self.page.update)

    def set_ui_enabled(self, enabled: bool):
        controls_to_disable = [
            self.client_id_entry, self.client_secret_entry, self.artist_search_entry, 
            self.connect_button, self.check_button, self.delete_playlist_button,
            self.playlist_name_entry, self.existing_playlist_entry, 
            self.playlist_mode_combo, self.sort_combo, self.album_check, 
            self.single_check, self.compilation_check, self.exclude_short_check, 
            self.public_check, self.artist_search_button
        ]
        
        for control in controls_to_disable:
            control.disabled = not enabled
            
        if enabled:
            if self.is_connected:
                self.start_flow_button.disabled = not bool(self.selected_artists)
                self.delete_playlist_button.disabled = False
            else:
                self.start_flow_button.disabled = True
                self.delete_playlist_button.disabled = True
        
        self.page.run_thread(self.page.update)

    def _check_initial_connection(self):
        if not self.client_id or not self.client_secret or self.client_id == CLIENT_ID:
            self.page.run_thread(lambda: self._update_status("Client ID/Secret Bekleniyor.", "warn"))
            return

        self._log("Spotipy cache kontrol ediliyor...", "cyan")
        auth_manager = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=REDIRECT_URI,
            scope=SCOPES,
            cache_path=SETTINGS_STORE.as_posix(),
            show_dialog=False
        )

        try:
            token = auth_manager.get_access_token(check_cache=True)
            if token and token.get('access_token'):
                self.sp = spotipy.Spotify(auth=token['access_token'])
                user = self.sp.current_user()
                if user:
                    self.current_user_id = user['id']
                    self.is_connected = True
                    self.page.run_thread(lambda: self._update_user_profile(user))
                    self.page.run_thread(lambda: self._update_status(f"BAĞLANDI: User ID: {self.current_user_id}", "succ"))
                    self.page.run_thread(lambda: self.set_ui_enabled(True))
                    return
            
        except (SpotifyException, requests.exceptions.RequestException, json.JSONDecodeError) as e:
            self._log(f"Token yenileme/Cache hatası: {e}", "warn")
        
        self.sp = None
        self.is_connected = False
        self.page.run_thread(lambda: self._update_status("Bağlantı Bekleniyor", "warn"))
        self.page.run_thread(self.page.update)


    def _connect_to_spotify_click(self, e: ft.ControlEvent):
        if not self.client_id_entry.value or not self.client_secret_entry.value:
            self._log("Client ID ve Client Secret girmelisiniz.", "error")
            return
        
        self.set_ui_enabled(False)
        self._update_status("Tarayıcıda onay bekleniyor...", "warn")
        self.connect_button.disabled = True
        self.page.update()
        
        self.page.run_thread(self._worker_connect)

    def _worker_connect(self):
        try:
            auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=REDIRECT_URI,
                scope=SCOPES,
                cache_path=SETTINGS_STORE.as_posix(),
                show_dialog=True
            )
            
            token_info = auth_manager.get_access_token(check_cache=False)
            
            if token_info and token_info.get('access_token'):
                self.sp = spotipy.Spotify(auth=token_info['access_token'])
                user = self.sp.current_user()
                self.current_user_id = user['id']
                self.is_connected = True
                self._log("Spotify bağlantısı ve token alımı başarılı!", "succ")
                self._update_user_profile(user)
                self._update_status(f"BAĞLANDI: User ID: {self.current_user_id}", "succ")
            else:
                raise Exception("Token alınamadı.")
                
        except Exception as ex:
            self.sp = None
            self.is_connected = False
            self._log(f"Bağlantı/Yetkilendirme Hatası: {ex}", "error")
            self._update_status("HATA: Bağlanılamadı. Logları Kontrol Et.", "err")
            
        finally:
            self.page.run_thread(lambda: self.set_ui_enabled(True))
            self.page.run_thread(lambda: setattr(self.connect_button, 'disabled', False))
            self.page.run_thread(self.page.update)
            
    def _quick_search_artist_click(self, e):
        if not self.sp: return self._log("Bağlı değilsiniz.", "error")
        search_term = self.artist_search_entry.value.strip()
        if search_term:
            self.set_ui_enabled(False)
            self._update_status(f"Sanatçı aranıyor: {search_term}", "info")
            threading.Thread(target=self._worker_search_artist, args=(search_term,)).start()

    def _worker_search_artist(self, search_term: str):
        try:
            data = self.search_artist(search_term)
            if data:
                self.current_artist_id = data.get('id')
                self._add_selected_artist(self.current_artist_id, data.get('name'))
                self._update_artist_info(data)
                self._update_status(f"Sanatçı bulundu: {data.get('name')}", "succ")
            else:
                self._log(f"Sanatçı '{search_term}' bulunamadı.", "warn")
                self._update_status(f"Sanatçı bulunamadı: {search_term}", "err")
                self._update_artist_info(None)
        except SpotifyException as e:
            self._log(f"Sanatçı arama hatası: {e}", "error")
            self._update_status("Arama Hatası.", "err")
        except Exception as e:
            self._log(f"Beklenmeyen arama hatası: {e}", "error")
        finally:
            self.page.run_thread(lambda: self.set_ui_enabled(True))

    def search_artist(self, name: str) -> Optional[dict]:
        if not self.sp: return None
        try:
            data = self.sp.search(q=f'artist:{name}', type='artist', limit=1)
            if data and data.get("artists", {}).get("items"):
                return data["artists"]["items"][0]
            return None
        except SpotifyException as e:
            self._log(f"API Hatası (Sanatçı Arama): {e}", "error")
            raise

    def delete_playlist(self, playlist_id: str) -> bool:
        if not self.sp: return False
        try:
            self.sp.playlist_unfollow(playlist_id)
            self._log(f"Playlist ID: {playlist_id} başarıyla silindi (unfollow edildi).", "succ")
            return True
        except SpotifyException as e:
            if "not found" in str(e) or "404" in str(e):
                self._log(f"Playlist silme hatası: ID '{playlist_id}' bulunamadı.", "warn")
                return True
            self._log(f"Playlist silme hatası (ID: {playlist_id}): {e}", "error")
            return False
        except Exception as e:
            self._log(f"Beklenmeyen playlist silme hatası: {e}", "error")
            return False

    async def _delete_playlist_click(self, e: ft.ControlEvent):
        if not self.sp:
            self._log("HATA: Spotify'a bağlı değilsiniz.", "error")
            return
        
        playlist_input = self.existing_playlist_entry.value.strip()
        playlist_id = self.playlist_id_from_input(playlist_input)

        if not playlist_id:
            self._log("HATA: Lütfen silmek istediğiniz Playlist ID/URL'sini girin.", "error")
            self._update_status("HATA: ID Eksik.", "err")
            return
        
        confirm = await self.page.open(ft.AlertDialog(
            modal=True,
            title=ft.Text("Onay Gerekiyor"),
            content=ft.Text(f"Bu eylem, '{playlist_id}' ID'li çalma listesini kütüphanenizden kaldıracaktır (unfollow). Devam etmek istediğinizden emin misiniz?"),
            actions=[
                ft.TextButton("Evet, Sil", on_click=lambda e: self.page.close(True), data=True),
                ft.TextButton("İptal", on_click=lambda e: self.page.close(False), data=False),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))
        
        if not confirm:
            return

        self.set_ui_enabled(False)
        self._update_status(f"Playlist ({playlist_id}) siliniyor...", "warn")
        
        threading.Thread(target=self._worker_delete_playlist, args=(playlist_id,)).start()
        
    def _worker_delete_playlist(self, playlist_id: str):
        try:
            success = self.delete_playlist(playlist_id)
            
            if success:
                self._update_status("SİLME BAŞARILI.", "succ")
                self._update_playlist_preview(None)
                self.page.run_thread(lambda: setattr(self.existing_playlist_entry, 'value', ''))
            else:
                self._update_status("SİLME HATASI! Logları Kontrol Edin.", "err")
        except Exception as ex:
            self._log(f"Silme Akışında Kritik Hata: {ex}", "error")
            self._update_status("KRİTİK HATA! Logları kontrol edin.", "err")
        finally:
            self.page.run_thread(lambda: self.set_ui_enabled(True))

    def _check_playlist_click(self, e):
        if not self.sp: return self._log("Bağlı değilsiniz.", "error")
        playlist_input = self.existing_playlist_entry.value.strip()
        playlist_id = self.playlist_id_from_input(playlist_input)
        
        if not playlist_id:
            self._log("Lütfen bir Playlist ID veya URL girin.", "warn")
            return

        self.set_ui_enabled(False)
        self._update_status(f"Playlist ({playlist_id}) kontrol ediliyor...", "info")
        threading.Thread(target=self._worker_check_playlist, args=(playlist_id,)).start()

    def _worker_check_playlist(self, playlist_id: str):
        try:
            playlist_data = self.sp.playlist(playlist_id)
            
            if playlist_data:
                self._log(f"Playlist bulundu: {playlist_data.get('name')}", "succ")
                self._update_status("Playlist Kontrol Başarılı.", "succ")
                self._update_playlist_preview(playlist_data)
            else:
                self._log(f"Playlist ID '{playlist_id}' bulunamadı.", "warn")
                self._update_status("Playlist Bulunamadı.", "err")
                self._update_playlist_preview(None)
                
        except SpotifyException as e:
            self._log(f"Playlist kontrol hatası: {e}", "error")
            self._update_status("Playlist Kontrol Hatası.", "err")
            self._update_playlist_preview(None)
        except Exception as e:
            self._log(f"Beklenmeyen kontrol hatası: {e}", "error")
        finally:
            self.page.run_thread(lambda: self.set_ui_enabled(True))
            
    def _get_album_types(self) -> List[str]:
        types = []
        if self.album_check.value:
            types.append('album')
        if self.single_check.value:
            types.append('single')
        if self.compilation_check.value:
            types.append('compilation')
        return types

    def _get_artist_albums(self, artist_id: str, album_types: List[str]) -> List[dict]:
        albums: Dict[str, dict] = {}
        for album_type in album_types:
            results = self.sp.artist_albums(artist_id, album_type=album_type, country='from_token', limit=50)
            while results:
                for item in results['items']:
                    # Aynı albümü farklı tiplerde (örn: single/album olarak) veya pazarlarda (country)
                    # tekrar eklememek için basit bir anahtar oluşturuyoruz.
                    album_key = item['name'].lower() + item['album_type'] + item['album_group']
                    if item['id'] not in albums: # ID bazlı benzersizlik kontrolü daha iyi
                        albums[item['id']] = item
                if results['next']:
                    results = self.sp.next(results)
                else:
                    results = None
        return list(albums.values())

    def _get_tracks_from_album(self, album_id: str, exclude_short: bool) -> List[str]:
        track_uris: List[str] = []
        results = self.sp.album_tracks(album_id)
        while results:
            for track in results['items']:
                if exclude_short and track.get('duration_ms', 0) < 60000:
                    continue
                track_uris.append(track['uri'])
            if results['next']:
                results = self.sp.next(results)
            else:
                results = None
        return track_uris

    def _get_artist_tracks_iceberg(self, artist_id: str, exclude_short: bool) -> List[str]:
        """
        Sanatçının Buzdağı modeline göre (10 Top, 10 Orta, 20 Derin) parça URI'lerini döndürür.
        Toplam maks. 40 parça.
        """
        if not self.sp: return []
        
        # 1. Top 10 (Zirve) Parçalar (Maks. 10)
        top_tracks_data = self.sp.artist_top_tracks(artist_id, country='from_token')
        top_tracks = [
            track['uri'] for track in top_tracks_data.get('tracks', []) 
            if track and track.get('uri') and (not exclude_short or track.get('duration_ms', 0) >= 60000)
        ][:10]
        
        # 2. Tüm Albüm/Single Parçalarını Topla
        album_types = self._get_album_types()
        all_albums = self._get_artist_albums(artist_id, album_types)
        
        all_album_uris: Set[str] = set()
        
        for album in all_albums:
            # Sadece ID'leri çekmek için mevcut _get_tracks_from_album'ü kullanabiliriz
            track_uris = self._get_tracks_from_album(album['id'], exclude_short)
            all_album_uris.update(track_uris)

        # Top 10'da zaten olanları hariç tut
        non_top_uris = list(all_album_uris - set(top_tracks))
        
        if not non_top_uris:
            self._log(f"Sanatçı ID: {artist_id} için Top 10 haricinde parça bulunamadı. Top 10 ile devam ediliyor.", "warn")
            return top_tracks
            
        # Benzersiz parçaların tam bilgilerini ve popülerliğini almak için
        non_top_track_details: List[dict] = []
        chunk_size = 50
        for i in range(0, len(non_top_uris), chunk_size):
            chunk = non_top_uris[i:i + chunk_size]
            try:
                # Spotify API'dan track detaylarını çekiyoruz (popülerlik bilgisi için)
                results = self.sp.tracks(chunk)
                if results and results.get('tracks'):
                    # Geçerli track'leri ve kısalık kontrolünü yaparak listeye ekle
                    non_top_track_details.extend([
                        track for track in results['tracks'] 
                        if track and track.get('uri') and (not exclude_short or track.get('duration_ms', 0) >= 60000)
                    ])
            except SpotifyException as e:
                self._log(f"Buzdağı parça detayları çekilirken hata: {e}", "error")
                
        
        # Popülerliğe Göre Sırala (Azalan)
        # Popülerliği bilinmeyen (None) veya 0 olan parçalar listenin sonuna düşer.
        non_top_track_details.sort(key=lambda t: t.get('popularity', -1), reverse=True)
        
        # 3. Katmanlama
        
        # Orta Katman (10 Şarkı)
        mid_tier_tracks = [track['uri'] for track in non_top_track_details[:10]]
        
        # Derin Kesim (20 Şarkı)
        # 10. indexten başla (11. parça), maks 20 tane al
        deep_cuts = [track['uri'] for track in non_top_track_details[10:30]] 

        # 4. Sonuçları Birleştir ve Max. 40'ı Garanti Et
        final_uris = top_tracks + mid_tier_tracks + deep_cuts
        
        self._log(
            f"Buzdağı Modu Sonuç: Top {len(top_tracks)}, Orta {len(mid_tier_tracks)}, Derin {len(deep_cuts)}. Toplam: {len(final_uris)}", 
            "cyan"
        )
        return final_uris

    def _create_or_manage_playlist(self, mode: str, name: str, existing_id: Optional[str], is_public: bool) -> str:
        if mode == "NEW":
            if not name:
                raise ValueError("Yeni playlist oluşturmak için bir isim girmelisiniz.")
            playlist = self.sp.user_playlist_create(
                user=self.current_user_id,
                name=name,
                public=is_public,
                description=f"PARADOX Flet tarafından oluşturuldu. Sanatçılar: {', '.join(self.selected_artists.values())}"
            )
            self._log(f"Yeni playlist oluşturuldu: {playlist['name']} ({playlist['id']})", "succ")
            return playlist['id']
        
        elif mode in ["OVERWRITE", "APPEND"]:
            if not existing_id:
                raise ValueError("Varolan bir playlist'i yönetmek için ID veya URL girmelisiniz.")
            
            try:
                playlist = self.sp.playlist(existing_id)
            except SpotifyException as e:
                if '404' in str(e):
                    raise SpotifyException(404, -1, f"Playlist ID '{existing_id}' bulunamadı.")
                raise e

            if mode == "OVERWRITE":
                self._log(f"Varolan playlist '{playlist['name']}' siliniyor (overwrite hazırlığı)...", "warn")
                # Overwrite için tüm parçaları temizleme:
                if playlist['tracks']['total'] > 0:
                    # Tüm parçaların snapshot ID'sini alıp toplu silme yapıyoruz
                    # 100'erli çekim yapıp siliyoruz
                    tracks_to_remove = []
                    results = self.sp.user_playlist_tracks(self.current_user_id, existing_id, limit=100)
                    while results:
                        tracks_to_remove.extend([
                            {'uri': item['track']['uri']} 
                            for item in results['items'] 
                            if item.get('track') and item['track'].get('uri')
                        ])
                        if results['next']:
                            results = self.sp.next(results)
                        else:
                            results = None
                            
                    # Sadece tekil URI'leri al
                    unique_uris_to_remove = list({t['uri']: t for t in tracks_to_remove}.values())
                    
                    if unique_uris_to_remove:
                         self.sp.playlist_remove_all_occurrences_of_items(existing_id, unique_uris_to_remove)
                         self._log(f"Playlist '{playlist['name']}' içerisindeki tüm parçalar ({len(unique_uris_to_remove)}) silindi.", "cyan")
                    else:
                        self._log(f"Playlist '{playlist['name']}' zaten boş veya parça bulunamadı.", "cyan")


            self._log(f"Playlist ID kullanılıyor: {playlist['name']} ({playlist['id']})", "succ")
            return playlist['id']
            
        else:
            raise ValueError("Geçersiz Playlist Modu.")
            
    def _add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> int:
        added_count = 0
        chunk_size = 100
        for i in range(0, len(track_uris), chunk_size):
            chunk = track_uris[i:i + chunk_size]
            self.sp.playlist_add_items(playlist_id, chunk)
            added_count += len(chunk)
            self._update_flow_stats("ADDING_TRACKS", current=i, total=len(track_uris), added=added_count)
            time.sleep(0.5) 
        return added_count
    
    def _upload_playlist_cover(self, playlist_id: str, image_url: Optional[str]):
        if not image_url:
            self._log("Playlist kapağı için sanatçı resmi bulunamadı.", "warn")
            return
        
        try:
            response = requests.get(image_url, stream=True)
            response.raise_for_status()
            
            img = Image.open(BytesIO(response.content))
            img = img.resize((300, 300)) 

            buffered = BytesIO()
            img.save(buffered, format="JPEG")
            
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')

            self.sp.playlist_upload_cover_image(playlist_id, base64_image)
            self._log("Playlist kapağı başarıyla güncellendi.", "succ")

        except Exception as e:
            self._log(f"Playlist kapağı yüklenirken hata oluştu: {e}", "error")

    def _start_flow_click(self, e):
        if not self.sp or not self.selected_artists: return self._log("Gerekli bilgiler eksik.", "error")
        self.set_ui_enabled(False)
        self._update_status("Akış Başlatıldı...", "info")
        threading.Thread(target=self._worker_main_flow).start()
    
    def _worker_main_flow(self):
        self._log("Ana akış başlatıldı: Albüm/Parça toplama ve Playlist oluşturma.", "warn")

        try:
            # 1. GEREKLİ AYARLARI AL
            album_types = self._get_album_types()
            exclude_short = self.exclude_short_check.value
            playlist_name = self.playlist_name_entry.value.strip()
            existing_playlist_input = self.existing_playlist_entry.value.strip()
            playlist_mode = self.playlist_mode_combo.value
            is_public = self.public_check.value
            sort_type = self.sort_combo.value
            
            if not self.selected_artists:
                raise ValueError("Lütfen en az bir sanatçı seçin.")
            if not album_types and sort_type != "ICEBERG":
                raise ValueError("Lütfen en az bir albüm tipi seçin (Album/Single/Compilation).")

            all_track_uris: Set[str] = set()
            final_track_list: List[str] = []
            
            # 2. PARÇALARI TOPLA (MODA GÖRE AYIRMA)
            
            if sort_type == "ICEBERG":
                self._log("Buzdağı Modu Etkin: Her sanatçıdan maks. 40 parça toplanıyor.", "warn")
                
                total_artists = len(self.selected_artists)
                for i, (artist_id, artist_name) in enumerate(self.selected_artists.items()):
                    self._log(f"[{i+1}/{total_artists}] Sanatçı için Buzdağı parçaları toplanıyor: {artist_name}", "cyan")
                    artist_tracks = self._get_artist_tracks_iceberg(artist_id, exclude_short)
                    all_track_uris.update(artist_tracks)
                    
                    self._update_flow_stats("TRACK_COUNT", current=len(all_track_uris), total=total_artists, added=0)
                    time.sleep(0.01)

                final_track_list = list(all_track_uris)

            else: # Normal Akış Modları (TRACK, POPULARITY, TOP_TRACKS)
                
                # Albüm toplama
                all_albums: List[dict] = []
                
                for artist_id, artist_name in self.selected_artists.items():
                    self._log(f"Sanatçı albümleri toplanıyor: {artist_name}", "cyan")
                    albums = self._get_artist_albums(artist_id, album_types)
                    all_albums.extend(albums)
                    
                self._log(f"Toplam {len(all_albums)} benzersiz albüm/single bulundu.", "succ")
                self._update_flow_stats("ALBUM_COUNT", current=0, total=len(all_albums), added=0)
                
                if not all_albums:
                    raise ValueError("Seçili kriterlere uygun albüm/single bulunamadı.")
                
                # Parça toplama
                for i, album in enumerate(all_albums):
                    album_name = album.get('name', 'Bilinmeyen Albüm')
                    self._log(f"[{i+1}/{len(all_albums)}] Albüm parçaları toplanıyor: {album_name}", "cyan")
                    
                    track_uris = self._get_tracks_from_album(album['id'], exclude_short)
                    all_track_uris.update(track_uris)
                    
                    self._update_flow_stats("ALBUM_COUNT", current=i + 1, total=len(all_albums), added=0)
                    self._update_flow_stats("TRACK_COUNT", current=len(all_track_uris), total=len(all_albums), added=0)
                    time.sleep(0.01)
                    
                final_track_list = list(all_track_uris)

                # Not: POPULARITY veya TOP_TRACKS sıralama mantığı burada uygulanabilir.
            
            self._log(f"Toplam {len(final_track_list)} benzersiz parça URI toplandı.", "succ")

            if not final_track_list:
                raise ValueError("Eklenecek parça bulunamadı.")

            # 3. PLAYLIST OLUŞTUR/YÖNET
            playlist_id = self._create_or_manage_playlist(
                mode=playlist_mode, 
                name=playlist_name, 
                existing_id=self.playlist_id_from_input(existing_playlist_input), 
                is_public=is_public
            )
            self.current_playlist_id = playlist_id
            
            # 4. PLAYLIST'E PARÇALARI EKLE
            self._log(f"Parçalar playlist'e ekleniyor (Toplam {len(final_track_list)} parça)...", "warn")
            self._update_flow_stats("ADDING_TRACKS", current=0, total=len(final_track_list), added=0)
            
            added_count = self._add_tracks_to_playlist(playlist_id, final_track_list)
            
            # 5. (OPSİYONEL) PLAYLIST KAPAĞINI YÜKLE
            self._upload_playlist_cover(playlist_id, self.current_artist_image_url)
            
            # 6. SONUÇLARI GÖSTER
            final_playlist_data = self.sp.playlist(playlist_id)
            
            self._log(f"Akış BAŞARILI. '{final_playlist_data['name']}' adlı playlist oluşturuldu/güncellendi. Toplam {added_count} parça eklendi.", "succ")
            self._update_status("AKIM TAMAMLANDI.", "succ")
            
            self.page.run_thread(self._update_playlist_preview, final_playlist_data, self.current_artist_image_url)

        except SpotifyException as ex:
            error_msg = f"Spotify API Hatası: {ex.http_status} - {ex.msg}"
            self._log(error_msg, "error")
            self._update_status("API HATASI! Logları Kontrol Edin.", "err")
            self.page.run_thread(lambda: setattr(self.flow_stats_wrapper, 'visible', False))

        except ValueError as ex:
            error_msg = f"Kullanıcı Girişi Hatası: {ex}"
            self._log(error_msg, "error")
            self._update_status("GİRİŞ HATASI! Logları Kontrol Edin.", "err")
            self.page.run_thread(lambda: setattr(self.flow_stats_wrapper, 'visible', False)) 
            
        except Exception as ex:
            self._log(f"Ana Akışta Kritik Hata: {ex}", "error")
            self._update_status("KRİTİK HATA! Logları kontrol edin.", "err")
            self.page.run_thread(lambda: setattr(self.flow_stats_wrapper, 'visible', False)) 

        finally:
            self.page.run_thread(lambda: self.set_ui_enabled(True))
    
def main(page: ft.Page):
    page.horizontal_alignment = ft.CrossAxisAlignment.CENTER
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.padding = 20
    page.window_width = 1000
    page.window_height = 800
    
    app = MainApp(page)

if __name__ == "__main__":
    if sys.platform.startswith('win'):
        import multiprocessing
        multiprocessing.freeze_support()
        
    ft.app(target=main)