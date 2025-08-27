def convertDate(date):
    """
    Convertit une date format (j,m,a) en nombre de jours au 21ème siècle (1 jour au 1er janvier 2000)
    """
    day,month,year=date
    daysByMonths=[31,28,31,30,31,30,31,31,30,31,30,31]
    nbDaysCentury=(year-2000)*365+(year-2000)//4+1*(year>2000) + sum(daysByMonths[0:month-1])+(year%4==0 and month>2)+day
    return nbDaysCentury

def reverseDate(nbDaysCentury):
    """
    Convertit un nombre de jours au 21ème siècle en date format numérique (j,m,a)
    """
    daysByMonths=[31,28,31,30,31,30,31,31,30,31,30,31]
    count=0
    year=1999
    while count<nbDaysCentury:
        year+=1
        count+=365+(year%4==0)
    nbDaysCentury-=(year-2000)*365+(year-2000)//4+1*(year>2000)
    count=0
    month=0
    if year%4==0:
        daysByMonths[1]+=1
    while count<nbDaysCentury:
        count+=daysByMonths[month]
        month+=1
    nbDaysCentury-=sum(daysByMonths[0:month-1])
    day=nbDaysCentury
    return day,month,year

def jourSemaine(nbDaysCentury):
    """
    Renvoie le jour de la semaine correspondant au nombre de jours depuis le 21eme siècle
    """
    jours=['lundi','mardi','mercredi','jeudi','vendredi','samedi','dimanche']
    return jours[(nbDaysCentury%7+4)%7]

def datePaques(an):
    """Calcule la date de Pâques d'une année donnée an (=nombre entier)"""
    a=an//100
    b=an%100
    c=(3*(a+25))//4
    d=(3*(a+25))%4
    e=(8*(a+11))//25
    f=(5*a+b)%19
    g=(19*f+c-e)%30
    h=(f+11*g)//319
    j=(60*(5-d)+b)//4
    k=(60*(5-d)+b)%4
    m=(2*j-k-g+h)%7
    n=(g-h+m+114)//31
    p=(g-h+m+114)%31
    jour=p+1
    mois=n
    return jour, mois, an

def joursFeries(an):
    """
    Renvoie la liste de tous les jours feries de l'année "an" en format nb jours au 21eme siècle
    """
    paques=convertDate(datePaques(an))
    lundiPaques=paques+1
    ascension=paques+39
    pentecote=paques+50
    nouvelAn=convertDate((1,1,an))
    feteTravail=convertDate((1,5,an))
    Armistice2=convertDate((8,5,an))
    FeteNat=convertDate((14,7,an))
    Assomption=convertDate((15,8,an))
    Toussaint=convertDate((1,11,an))
    Armistice1=convertDate((11,11,an))
    Noel=convertDate((25,12,an))
    L= sorted([lundiPaques,ascension,pentecote,nouvelAn,feteTravail,Armistice2,FeteNat,Assomption,Toussaint,Armistice1,Noel])
    return [reverseDate(date) for date in L]