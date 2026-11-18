"""
Photos de profil : vérification puis nettoyage avec Pillow.
On ne fait JAMAIS confiance au fichier reçu : on le décode, puis on fabrique une image neuve.
"""
from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

TAILLE_MAX = 5 * 1024 * 1024          # 5 Mo
PIXELS_MAX = 40_000_000               # 40 mégapixels : protège contre les « bombes de décompression »
FORMATS_ACCEPTES = {"JPEG", "PNG", "WEBP"}
COTE = 400                            # photo finale : 400 × 400 px


class ImageInvalide(Exception):
    """Message compréhensible par l'étudiant."""


def preparer_avatar(fichier):
    """Vérifie l'image envoyée et renvoie les octets d'une photo WebP carrée, propre et légère."""
    if fichier.size > TAILLE_MAX:
        raise ImageInvalide("L'image dépasse 5 Mo.")

    try:
        image = Image.open(fichier)    # lit seulement l'en-tête : format et dimensions
        if image.format not in FORMATS_ACCEPTES:
            raise ImageInvalide("Formats acceptés : JPEG, PNG ou WebP.")
        if image.width * image.height > PIXELS_MAX:
            raise ImageInvalide("Image trop grande (40 mégapixels maximum).")
        image.load()                   # décode vraiment : un fichier corrompu ou piégé échoue ici
    except ImageInvalide:
        raise
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError, SyntaxError, ValueError) as exc:
        raise ImageInvalide("Ce fichier n'est pas une image valide.") from exc

    image = ImageOps.exif_transpose(image)   # photo de téléphone : on respecte son orientation

    # Transparence (PNG) → fond blanc, sinon les zones transparentes deviendraient noires
    if image.mode in ("RGBA", "LA", "P"):
        image = image.convert("RGBA")
        fond = Image.new("RGB", image.size, (255, 255, 255))
        fond.paste(image, mask=image.getchannel("A"))
        image = fond
    else:
        image = image.convert("RGB")

    image = ImageOps.fit(image, (COTE, COTE), method=Image.Resampling.LANCZOS)   # carré, centré

    # Image NEUVE : seuls les pixels sont copiés, aucune métadonnée (GPS, appareil…) ne survit
    propre = Image.new("RGB", image.size)
    propre.paste(image)

    sortie = BytesIO()
    propre.save(sortie, format="WEBP", quality=85)
    return sortie.getvalue()