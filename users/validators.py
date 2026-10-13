from django.core.exceptions import ValidationError
from django.db.models import Q
from .models import CustomUser

# Curated blocklist of known disposable, temporary, and burner email providers
DISPOSABLE_EMAIL_DOMAINS = frozenset({
    # Major temp mail services
    "10minutemail.com", "10minutemail.net", "10minutemail.org", "10minutemail.co.za",
    "10minmail.com", "1secmail.com", "1secmail.net", "1secmail.org",
    "temp-mail.org", "temp-mail.io", "temp-mail.ru", "temp-mail.de",
    "tempmail.com", "tempmail.net", "tempmail.org", "tempmail.plus", "tempmail.io",
    "tempmail.dev", "tempmail.co", "tempmail.de", "tempmail.eu", "tempmail.it",
    "tempmail.us", "tempmail2.com", "tempmailo.com", "tempail.com", "tempinbox.com",
    "tempinbox.co.uk", "tempemail.com", "tempemail.net", "tempemail.biz",
    "tempmailer.com", "tempmailer.de", "tempomail.fr", "tempymail.com",
    "tmpmail.net", "tmpmail.org", "tmpmail.com", "tmpbox.net", "tmail.ws",
    "tmailservices.com", "tmailinator.com",
    # YOPmail family
    "yopmail.com", "yopmail.fr", "yopmail.net", "cool.fr.nf", "jetable.fr.nf",
    "courriel.fr.nf", "moncourrier.fr.nf", "monemail.fr.nf", "monmail.fr.nf",
    # Mailinator family
    "mailinator.com", "mailinator.net", "mailinator.org", "mailinator2.com",
    "sogetthis.com", "mailin8r.com", "mailtothis.com", "tradermail.info",
    "veryrealemail.com", "notmailinator.com",
    # GuerrillaMail family
    "guerrillamail.com", "guerrillamail.net", "guerrillamail.org", "guerrillamail.biz",
    "guerrillamail.de", "guerrillamail.info", "guerrillamailblock.com",
    "sharklasers.com", "grr.la", "pokemail.net", "spam4.me",
    # GetNada / Nada family
    "getnada.com", "nada.email", "nada.ltd", "abyssmail.com", "boximail.com",
    "clrmail.com", "dropjar.com", "getairmail.com", "givmail.com", "inboxbear.com",
    "robot-mail.com", "tafmail.com", "vomoto.com", "zetmail.com",
    # TrashMail / Wegwerfmail family
    "trashmail.com", "trashmail.net", "trashmail.org", "trashmail.me", "trashmail.io",
    "trashmail.de", "trashmail.at", "trash-mail.com", "trash-mail.de", "trash-mail.at",
    "trashcanmail.com", "trashdevil.com", "trashdevil.de", "trashemail.de",
    "trashmailer.com", "trashymail.com", "trashymail.net", "kurzepost.de",
    "objectmail.com", "proxymail.eu", "rcpt.at", "wegwerfmail.de", "wegwerfmail.net",
    "wegwerfmail.org", "wegwerfmail.info", "wegwerfemail.com", "wegwerfemail.de",
    "wegwerfadresse.de", "mytrashmail.com",
    # 1secmail domains
    "wwjmp.com", "esiix.com", "xojxe.com", "yoggm.com", "dcctb.com", "kzccv.com",
    "qiott.com", "wuuvo.com", "icznn.com", "ezztt.com", "vjuum.com", "laafd.com",
    "txcct.com", "dpptd.com", "rteet.com",
    # Other well-known disposable providers
    "maildrop.cc", "dispostable.com", "mohmal.com", "mohmal.in", "mohmal.tech",
    "mohmal.im", "emailondeck.com", "internxt.com", "mailnesia.com", "mintemail.com",
    "mytemp.email", "mytempemail.com", "mytempmail.com", "burnermail.io", "burner.kiwi",
    "fakemail.net", "fakemailgenerator.com", "fakeinbox.com", "emailfake.com",
    "generator.email", "crazymailing.com", "luxusmail.org", "mailpoof.com",
    "throwawaymail.com", "throwawayemailaddress.com", "throwam.com", "throam.com",
    "mailcatch.com", "mailnull.com", "mailsac.com", "mailslurp.com",
    "mailtemp.info", "mailtemp.net", "maildu.de", "mailforspam.com",
    "mailfreeonline.com", "mailfs.com", "mailguard.me", "mailhazard.com",
    "mailhz.me", "mailimate.com", "mailismagic.com", "mailmate.com",
    "mailme.ir", "mailme.lv", "mailme24.com", "mailmetrash.com", "mailmoat.com",
    "mailms.com", "mailna.biz", "mailna.co", "mailna.in", "mailna.me",
    "mailox.fun", "mailpick.biz", "mailproxsy.com", "mailquack.com", "mailrock.biz",
    "mailscrap.com", "mailseal.de", "mailshell.com", "mailsiphon.com",
    "mailslapping.com", "mailslite.com", "mailtome.de", "mailtv.net", "mailzi.ru",
    "mailzilla.com", "mailzilla.org", "harakirimail.com", "incognitomail.org",
    "incognitomail.com", "incognitomail.net", "jetable.com", "jetable.net",
    "jetable.org", "kasmail.com", "koszmail.pl", "letthemeatspam.com",
    "litedrop.com", "lopl.co.cc", "lortemail.dk", "meltmail.com", "mierdamail.com",
    "migumail.com", "moakt.com", "moakt.cc", "moakt.co", "moakt.ws",
    "monumentmail.com", "mt2009.com", "mt2014.com", "mt2015.com",
    "mycleaninbox.net", "myemailboxy.com", "mymail-in.net", "mymailoasis.com",
    "myphantomemail.com", "myspamless.com", "nabuma.com", "neomailbox.com",
    "neverbox.com", "nobulk.com", "noclickemail.com", "nogmailspam.info",
    "nomail.xl.cx", "nomail2me.com", "nomorespamemails.com", "nonspam.eu",
    "nonspammer.de", "noref.in", "nospam4.us", "nospamfor.us", "nospamthanks.info",
    "nowmymail.com", "nurfuerspam.de", "oneoffemail.com", "onewaymail.com",
    "opayq.com", "otherinbox.com", "outlawspam.com", "owlpic.com", "pancakemail.com",
    "pookmail.com", "prtnx.com", "punkass.com", "quickinbox.com", "recode.me",
    "reconmail.com", "recursor.net", "recyclemail.dk", "regbypass.com",
    "rejectmail.com", "rhyta.com", "rklips.com", "rmqkr.net", "rppkn.com",
    "rtrtr.com", "s0ny.net", "safe-mail.net", "safersignup.de", "safetymail.info",
    "safetypost.de", "sandelf.de", "saynotospams.com", "schafmail.de",
    "secretemail.de", "secure-mail.biz", "selfdestructingmail.com", "sendspamhere.com",
    "sharedmailbox.org", "shieldedmail.com", "shiftmail.com", "shitmail.me",
    "shitmail.org", "shortmail.net", "sibmail.com", "skeefmail.com", "slaskpost.se",
    "slopsbox.com", "smashmail.de", "smellfear.com", "snakemail.com", "sneakemail.com",
    "snkmail.com", "sofimail.com", "sofort-mail.de", "solvemail.info", "soodomail.com",
    "soodonims.com", "spam.la", "spam.su", "spamavert.com", "spambob.com",
    "spambob.net", "spambob.org", "spambog.com", "spambog.de", "spambog.net",
    "spambog.ru", "spambox.info", "spambox.us", "spamcannon.com", "spamcannon.net",
    "spamcero.com", "spamcon.org", "spamcorptastic.com", "spamcowboy.com",
    "spamday.com", "spamex.com", "spamfree.eu", "spamfree24.com", "spamfree24.de",
    "spamfree24.eu", "spamfree24.info", "spamfree24.net", "spamfree24.org",
    "spamgoes.in", "spamgourmet.com", "spamgourmet.net", "spamgourmet.org",
    "spamherelots.com", "spamhereplease.com", "spamhole.com", "spamify.com",
    "spaminator.de", "spamkill.info", "spaml.com", "spaml.de", "spammotel.com",
    "spamobox.com", "spamoff.de", "spamsalad.in", "spamslicer.com", "spamspot.com",
    "spamstack.net", "spamthis.co.uk", "spamthisplease.com", "spamtrail.com",
    "spamtroll.net", "spoofmail.de", "squizzy.de", "ssoia.com", "startkeys.com",
    "stop-my-spam.com", "streetwisemail.com", "stuffmail.de", "supergreatmail.com",
    "superrito.com", "suremail.info", "talkinator.com", "techemail.com",
    "teleworm.com", "teleworm.us", "tempalias.com", "tempe-mail.com",
    "temporarily.de", "temporarioemail.com.br", "temporaryemail.net",
    "temporaryemail.us", "temporaryforwarding.com", "temporaryinbox.com",
    "temporarymailaddress.com", "thanksnospam.info", "thankyou2010.com",
    "thisisnotmyrealemail.com", "thismail.net", "thismail.ru", "tilien.com",
    "tittbit.in", "toiea.com", "toomail.biz", "topranklist.de", "trbvm.com",
    "trbvn.com", "trialmail.de", "trickmail.net", "trillianpro.com", "tryalert.com",
    "turual.com", "twinmail.de", "tyldd.com", "uggsrock.com", "umail.net",
    "upliftnow.com", "uplipht.com", "uroid.com", "valemail.net", "venompen.com",
    "viditag.com", "viewcastmedia.com", "vubby.com", "webemail.me", "webm4il.info",
    "wh4f.org", "whatiaas.com", "whatpaas.com", "whopy.com", "whyspam.me",
    "willselfdestruct.com", "winemaven.info", "wronghead.com", "wuzup.net",
    "wuzupmail.net", "xagloo.com", "xemaps.com", "xents.com", "xmaily.com",
    "xoxy.net", "yapped.net", "yep.it", "yogamaven.com", "yuurok.com",
    "zehnminuten.de", "zehnminutenmail.de", "zippymail.info", "zoaxe.com",
    "zoemail.com", "zoemail.net", "zoemail.org", "zomg.info",
    "anonbox.net", "dropmail.me", "instantemailaddress.com", "mailhero.io",
})

# Keywords in domain names that indicate a disposable/burner mail service
DISPOSABLE_DOMAIN_KEYWORDS = (
    "tempmail", "temp-mail", "tmpmail", "tmp-mail", "tempinbox", "tempemail",
    "temporarymail", "temporaryemail", "10minutemail", "10minmail", "minutemail",
    "1secmail", "throwaway", "trashmail", "trash-mail", "trashemail",
    "fakemail", "fakeinbox", "emailfake", "burnermail", "disposable",
    "dispostable", "mailinator", "guerrillamail", "yopmail", "sharklasers",
    "maildrop", "getnada", "mohmal", "emailondeck", "spam4", "spambog",
    "spambox", "spamgourmet", "spamfree", "spammotel", "wegwerf", "jetable",
    "harakirimail", "incognitomail", "mailnesia", "mintemail", "mytemp",
    "tempail", "crazymailing", "mailpoof", "mailsac", "mailslurp",
    "mailcatch", "mailnull", "dropmail", "anonbox",
)

# High-abuse free TLDs heavily used by automated temp-mail generators
BLOCKED_DISPOSABLE_TLDS = (".tk", ".ml", ".ga", ".cf", ".gq")

# Common typosquatted/fake domains for major email providers
TYPOSQUATTED_DOMAINS = {
    "gmai1.com": "gmail.com",
    "gmial.com": "gmail.com",
    "gamil.com": "gmail.com",
    "gmal.com": "gmail.com",
    "gmail.co": "gmail.com",
    "gmail.con": "gmail.com",
    "gmaill.com": "gmail.com",
    "gmail.org": "gmail.com",
    "gmail.net": "gmail.com",
    "yaho.com": "yahoo.com",
    "yahooo.com": "yahoo.com",
    "yaho.co.in": "yahoo.co.in",
    "outlok.com": "outlook.com",
    "outllok.com": "outlook.com",
    "hotmial.com": "hotmail.com",
    "hotmal.com": "hotmail.com",
}


def is_disposable_email_domain(domain: str) -> bool:
    """Returns True if the domain belongs to a known disposable or temporary email service."""
    domain = domain.strip().lower().rstrip(".")
    if not domain:
        return True

    # Check exact domain and any parent domain (e.g. mail.temp-mail.org -> temp-mail.org)
    parts = domain.split(".")
    for i in range(len(parts) - 1):
        sub = ".".join(parts[i:])
        if sub in DISPOSABLE_EMAIL_DOMAINS:
            return True

    # Check heuristic keywords
    for kw in DISPOSABLE_DOMAIN_KEYWORDS:
        if kw in domain:
            return True

    # Check high-abuse disposable TLDs
    if domain.endswith(BLOCKED_DISPOSABLE_TLDS):
        return True

    return False


def validate_unique_and_legitimate_email(email: str, exclude_user_id=None) -> str:
    """
    Validates that an email address is:
    1. Present and properly formatted.
    2. Not using '+' subaddressing aliases.
    3. Not from a disposable / temporary / burner email provider.
    4. Not a typosquatted fake domain (e.g. gmai1.com).
    5. Unique across all accounts (including Gmail dot-insensitive matching).
    Returns the normalized (lowercased, stripped) email string.
    """
    email = (email or "").strip().lower()
    if not email or "@" not in email:
        raise ValidationError("Please enter a valid email address.")

    local_part, domain = email.rsplit("@", 1)
    if not local_part or not domain or "." not in domain:
        raise ValidationError("Please enter a valid email address.")

    # Block '+' subaddressing so one email cannot register multiple profiles (e.g. user+1@gmail.com)
    if "+" in local_part:
        raise ValidationError(
            "Email aliases containing '+' are not allowed. Please enter your primary email address."
        )

    # Check for typosquatted fake domains
    if domain in TYPOSQUATTED_DOMAINS:
        suggested = TYPOSQUATTED_DOMAINS[domain]
        raise ValidationError(
            f"Invalid email domain '{domain}'. Did you mean '{suggested}'?"
        )

    # Block disposable / temporary email domains
    if is_disposable_email_domain(domain):
        raise ValidationError(
            "Temporary or disposable email addresses are not allowed. Please use a permanent personal email address (such as Gmail, Yahoo, Outlook, or iCloud)."
        )

    # Check uniqueness across CustomUser accounts
    qs = CustomUser.objects.all()
    if exclude_user_id is not None:
        qs = qs.exclude(pk=exclude_user_id)

    if qs.filter(email__iexact=email).exists():
        raise ValidationError(
            "An account with this email address already exists. Please log in or use a different email."
        )

    # Prevent Gmail / Googlemail dot-variation duplicates (e.g. a.b@gmail.com vs ab@gmail.com)
    if domain in ("gmail.com", "googlemail.com"):
        canonical_local = local_part.replace(".", "")
        existing_gmails = qs.filter(
            Q(email__iendswith="@gmail.com") | Q(email__iendswith="@googlemail.com")
        ).values_list("email", flat=True)

        for existing_email in existing_gmails:
            if existing_email and "@" in existing_email:
                ex_local, _ = existing_email.strip().lower().rsplit("@", 1)
                ex_canonical = ex_local.split("+")[0].replace(".", "")
                if ex_canonical == canonical_local:
                    raise ValidationError(
                        "An account with this email address already exists. Please log in or use a different email."
                    )

    return email
