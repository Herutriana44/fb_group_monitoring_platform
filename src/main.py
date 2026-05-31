import asyncio
import logging
import argparse
from auth import login
from collector import GroupCollector
from processor import PostProcessor
from notifier import Notifier

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    parser = argparse.ArgumentParser(description="Facebook Group Monitor CLI")
    parser.add_argument('--action', choices=['login', 'monitor'], required=True, help="Action to perform")
    # Uncomment jika argumen ini nanti digunakan kembali
    # parser.add_argument('--user', help="Facebook email")
    # parser.add_argument('--pass', dest='password', help="Facebook password")
    
    args = parser.parse_args()

    if args.action == 'login':
        if not getattr(args, 'user', None) or not getattr(args, 'password', None):
            logger.error("Username and password are required for login.")
            return
        await login(args.user, args.password)
        
    elif args.action == 'monitor':
        logger.info("Starting monitoring process... (Tekan Ctrl+C untuk berhenti)")
        collector = GroupCollector(group_id="27422186357398808")
        processor = PostProcessor(keywords=["lelang", "jual"])
        notifier = Notifier()
        
        # Interval waktu cek (dalam detik). Contoh: 300 detik = 5 menit sekali
        # Sesuaikan dengan kebutuhan agar tidak terkena checkpoint/banned Facebook
        CHECK_INTERVAL = 300 

        try:
            while True:
                logger.info("Memulai scanning feed terbaru...")
                
                try:
                    posts = await collector.fetch_feed()
                    matches = processor.process_posts(posts)
                    
                    for match in matches:
                        notifier.notify(f"Match found: {match[:100]}...")
                        
                    logger.info("Scanning selesai. Menunggu untuk jadwal berikutnya.")
                except Exception as e:
                    # Menangkap error di dalam loop agar jika ada 1 error (misal jaringan putus),
                    # aplikasi tidak langsung mati dan tetap mencoba lagi nanti.
                    logger.error(f"Terjadi error saat monitoring: {e}")

                # Jeda waktu sebelum melakukan monitoring berikutnya
                logger.info(f"Tidur selama {CHECK_INTERVAL} detik...")
                await asyncio.sleep(CHECK_INTERVAL)
                
        except asyncio.CancelledError:
            # Menangani jika task di-cancel oleh asyncio
            logger.info("Monitoring dihentikan.")
        except KeyboardInterrupt:
            # Menangani jika user menekan Ctrl+C (pada beberapa sistem operasi)
            logger.info("Aplikasi dihentikan oleh pengguna (Ctrl+C).")
        finally:
            logger.info("Sesi monitoring ditutup dengan aman.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # Menangkap KeyboardInterrupt pada level paling luar (Windows/Linux)
        print("\n[Muted] Monitoring dihentikan melalui terminal.")