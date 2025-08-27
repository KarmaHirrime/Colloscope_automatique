import math
import utilitaires as ut
import xml.etree.ElementTree as ET
from datetime import date,timedelta

# %% Définition de la classe "colleur"

class colleur:
    def __init__(self,id,nom,horaires,heures):
        self.nom=nom #Nom à afficher dans le colloscope
        self.id=id #Identifiant unique du colleur
        self.horaires=horaires #La liste des horaires du colleur
        self.matieres=[matiere for matiere in heures] #La liste des matieres du colleur
        self.heures=heures #Un dictionnaire avec en clé les matières du colleur et en valeurs le nombre d'heures du colleur dans cette matiere (pas forcément entier)

    def to_xml(self):
        from xml.etree.ElementTree import Element, SubElement

        elem = Element("Colleur", attrib={"id": str(self.id)})
        SubElement(elem, "Nom").text = self.nom

        horaires_elem = SubElement(elem, "Horaires")
        for horaire in self.horaires:
            SubElement(horaires_elem, "Ref", attrib={"id": horaire.id})

        heures_elem = SubElement(elem, "Heures")
        for matiere, nb_heures in self.heures.items():
            mat_elem = SubElement(heures_elem, "Heure", attrib={"matiere": matiere.id})
            mat_elem.text = str(nb_heures)

        return elem

    @staticmethod
    def from_xml(elem):
        id_ = elem.attrib["id"]
        nom = elem.find("Nom").text

        horaires_ids = [ref.attrib["id"] for ref in elem.find("Horaires").findall("Ref")]
        heures_dict = {h.attrib["matiere"]: float(h.text) for h in elem.find("Heures").findall("Heure")}

        # Pour l'instant, on ne connaît pas encore les objets matière ni horaires,
        # on met les identifiants en attente
        return colleur(id_, nom, horaires=horaires_ids, heures=heures_dict)

    def resolve(self, db):
        # Résolution des horaires : on suppose que db["horaires"] est un dict {id: horaire}
        self.horaires = [db["horaires"][hid] for hid in self.horaires]

        # Résolution des matières : db["matieres"] est un dict {id: matiere}
        self.heures = {db["matieres"][mid]: h for mid, h in self.heures.items()}

        # Mise à jour automatique de la liste des matières
        self.matieres = list(self.heures.keys())


# %% Définition de la classe "horaire"

class horaire:
    def __init__(self,id,jour,debut,duree,semaines,flexible,matieres,options,places,colleur,salle=None):
        self.id=id
        self.jour=jour #Chaine de caractere
        self.debut=debut #int, nombre de minutes ecoulees depuis minuit au debut de l'horaire
        self.duree=duree #En minutes, int
        self.semaines=semaines #La liste des semaines ou cet horaire est disponible
        self.flexible=flexible #Booléen. Si True, cela signifie que c'est l'horaire prioritaire a dégager en cas d'heures non entières pour le colleur. A priori toujours False pour un TD/TP ou pour un horaire d'edt
        self.matieres=matieres #Une liste de matieres (avec classe associée). L'horaire sera uniquement disponible pour les matières/classes dans la liste. None si non pertinent
        self.options=options #Une liste d'options. L'horaire sera uniquement disponible pour les étudiants qui ont une option parmi celles dans la liste. Si l'horaire est un créneau edt, cela signifie que les étudiants avec une option dans la liste seront indisponibles pour les colles ou TP sur cet horaire. Devrait être initialisé à toutes les options possibles pour un horaire de colleur
        self.places=places #Le nombre de places disponible pour cet horaire si pertinent
        self.colleur=colleur #Le colleur associé à cet horaire, None si non pertinent (horaire de TP)
        if salle:
            self.salle=salle #La salle où a lieu la colle, chaine vide si horaire de TP ou d'edt
        else:
            self.salle=""

    def to_xml(self):
        elem = ET.Element("Horaire", attrib={"id": str(self.id)})
        ET.SubElement(elem, "Jour").text = self.jour
        ET.SubElement(elem, "Debut").text = str(self.debut)
        ET.SubElement(elem, "Duree").text = str(self.duree)
        s_elem = ET.SubElement(elem, "Semaines")
        for s in self.semaines:
            ET.SubElement(s_elem, "Semaine").text = str(s)
        ET.SubElement(elem, "Flexible").text = str(int(self.flexible))
        m_elem = ET.SubElement(elem, "Matieres")
        for m in self.matieres:
            ET.SubElement(m_elem, "MatiereID").text = str(m.id if hasattr(m, 'id') else m)
        o_elem = ET.SubElement(elem, "Options")
        for o in self.options:
            ET.SubElement(o_elem, "Option").text = o
        ET.SubElement(elem, "Places").text = str(self.places)
        if self.colleur:
            ET.SubElement(elem, "ColleurID").text = str(self.colleur.id if hasattr(self.colleur, 'id') else self.colleur)
        ET.SubElement(elem,"Salle").text=self.salle
        return elem

    @staticmethod
    def from_xml(elem):
        id = elem.attrib["id"]
        jour = elem.find("Jour").text
        debut = int(elem.find("Debut").text)
        duree = int(elem.find("Duree").text)
        semaines = [int(s.text) for s in elem.find("Semaines").findall("Semaine")]
        flexible = bool(int(elem.find("Flexible").text))
        matieres = [m.text for m in elem.find("Matieres").findall("MatiereID")]
        options = [o.text for o in elem.find("Options").findall("Option")]
        places = int(elem.find("Places").text)
        colleur = elem.findtext("ColleurID")
        salle=elem.find("Salle").text
        return horaire(id, jour, debut, duree, semaines, flexible, matieres, options, places, colleur,salle)

    def resolve(self, db):
        resolved=[]
        for m in self.matieres:
            try:
                resolved.append(db["matieres"][m])
            except:
                resolved.append(db["TPs"][m])
        self.matieres = [mt for mt in resolved]
        self.colleur = db["colleurs"].get(self.colleur)

    def overlap(self,h2,semaine):
        """
        h2 est un autre objet "horaire"
        semaine un numéro de semaine
        Renvoie True si les deux horaires se chevauchent (strictement, on autorise la téléportation des étudiants), False sinon. On néglige le cas d'horaires se chevauchant avant/après minuit. Si vous êtes dans ce cas, je pense que c'est illégal !
        """
        if semaine not in self.semaines or semaine not in h2.semaines: #Si l'un des deux horaires n'est pas disponible cette semaine, pas de problème
            return False
        if self.jour!=h2.jour: #Si les deux horaires ne sont pas le même jour, pas de problème. Attention, il faut avoir géré la casse pour les jours et avoir évité les abréviations
            return False
        if (self.debut<=h2.debut and self.debut+self.duree>h2.debut) or (h2.debut<=self.debut and h2.debut+h2.duree>self.debut):
            return True
        return False

# %% Définition de la classe "matiere"

class matiere:
    def __init__(self,id,nom,classe,periodes,nbCollesMax,dureeColle,dureePreparation,groupes_fixes,colleurs,places,alternance_fixe,decalage_semaines):
        self.id=id
        self.nom=nom #Le nom de la matière pour l'affichage dans le colloscope (attention, sert d'indentifiant si option n'est pas None)
        self.classe=classe #La classe concernée pour cette matière
        self.periodes=periodes #Un dictionnaire dont les clés sont des options (chaînes de caractères) et les valeurs des chaines de caracteres avec des 0 et des 1 representant les occurences des colles de cette matiere avec cette option sur une periode donnée. Attention, les étudiants ne devraient avoir qu'au plus une option parmis les options dans les clés du dictionnaire.
        self.nbCollesMax=nbCollesMax #Le nombre de colles maximum dans l'année pour cette matière (permet de gérer le français en deuxième année), egal a 40 si non pertinent
        self.dureeColle=dureeColle #La duree de la colle en minutes
        self.dureePreparation=dureePreparation #La duree de la preparation en minutes (le colleur est disponible pendant la preparation de ou des éleves mais pas les éleves)
        self.groupes_fixes=groupes_fixes #Booléen. Si True, les élèves d'un même groupe passent la colle ensemble, si False le programme ne tiendra pas compte des groupes de colles
        self.colleurs=colleurs #La liste des colleurs associés à la matière
        self.options=[o for o in periodes]
        self.places=places #le nombre de places en colle de cette matiere sur un creneau donné
        self.alternance_fixe=alternance_fixe #Si True, cette matiere sera groupée avec les autres matieres alternance_fixe, les etudiants auront la meme alternance sur les matieres alternance_fixe. Si False, une variable d'alternance spécifique sera créée.
        self.decalage_semaines=decalage_semaines

    def to_xml(self):
        elem = ET.Element("Matiere", attrib={"id": str(self.id)})
        ET.SubElement(elem, "Nom").text = self.nom
        ET.SubElement(elem, "ClasseID").text = str(self.classe.id if hasattr(self.classe, 'id') else self.classe)
        p_elem = ET.SubElement(elem, "Periodes")
        for opt, val in self.periodes.items():
            per = ET.SubElement(p_elem, "Periode", attrib={"option": opt})
            per.text = val
        ET.SubElement(elem, "NbCollesMax").text = str(self.nbCollesMax)
        ET.SubElement(elem, "DureeColle").text = str(self.dureeColle)
        ET.SubElement(elem, "DureePreparation").text = str(self.dureePreparation)
        ET.SubElement(elem, "GroupesFixes").text = str(int(self.groupes_fixes))
        c_elem = ET.SubElement(elem, "Colleurs")
        for c in self.colleurs:
            ET.SubElement(c_elem, "ColleurID").text = str(c.id if hasattr(c, 'id') else c)
        ET.SubElement(elem, "Places").text = str(self.places)
        ET.SubElement(elem, "AlternanceFixe").text = str(int(self.alternance_fixe))
        ET.SubElement(elem,"DecalageSemaines").text=str(int(self.decalage_semaines))
        return elem

    @staticmethod
    def from_xml(elem):
        id = elem.attrib["id"]
        nom = elem.find("Nom").text
        classe = elem.find("ClasseID").text
        periodes = {p.attrib["option"]: p.text for p in elem.find("Periodes").findall("Periode")}
        nbCollesMax = int(elem.find("NbCollesMax").text)
        dureeColle = int(elem.find("DureeColle").text)
        dureePreparation = int(elem.find("DureePreparation").text)
        groupes_fixes = bool(int(elem.find("GroupesFixes").text))
        colleurs = [c.text for c in elem.find("Colleurs").findall("ColleurID")]
        places = int(elem.find("Places").text)
        alternance_fixe = bool(int(elem.find("AlternanceFixe").text))
        if elem.find("DecalageSemaines") is not None:
            decalage_semaines=int(elem.find("DecalageSemaines").text)
        else:
            decalage_semaines=0
        return matiere(id, nom, classe, periodes, nbCollesMax, dureeColle, dureePreparation, groupes_fixes, colleurs, places, alternance_fixe,decalage_semaines)

    def resolve(self, db):
        self.classe = db["classes"][self.classe]
        self.colleurs = [db["colleurs"][c] for c in self.colleurs]


# %% Définition de la classe "TP"

class TP:
    def __init__(self,id,nom,classe,periodes,horaires,groupes_fixes,places,alternance_fixe,decalage_semaines):
        self.id=id
        self.nom=nom #Le nom du TP/TD
        self.classe=classe #La classe concernée pour ce TP/TD
        self.periodes=periodes #Un dictionnaire dont les clés sont des options (chaînes de caractères) et les valeurs des chaines de caracteres avec des 0 et des 1 representant les occurences des TP avec cette option sur une periode donnée. Attention, les étudiants ne devraient avoir qu'au plus une option parmi les options dans les clés du dictionnaire.
        self.horaires=horaires #La liste d'horaires disponibles pour ce TD/TP, les options sont rattachées directement aux horaires
        self.groupes_fixes=groupes_fixes #Booléen. Si True, les élèves d'un même groupe doivent être présents au même horaire sur ce TP
        self.places=places #Le nombre de places maximum sur ce TP (peut être modulé si besoin pour les horaires)
        self.options=[o for o in periodes]
        self.alternance_fixe=alternance_fixe #Si True, cette matiere sera groupée avec les autres matieres alternance_fixe, les etudiants auront la meme alternance sur les matieres alternance_fixe. Si False, une variable d'alternance spécifique sera créée.
        self.decalage_semaines=decalage_semaines

    def to_xml(self):
        elem = ET.Element("TP", attrib={"id": str(self.id)})
        ET.SubElement(elem, "Nom").text = self.nom
        ET.SubElement(elem, "ClasseID").text = str(self.classe.id if hasattr(self.classe, 'id') else self.classe)
        p_elem = ET.SubElement(elem, "Periodes")
        for opt, val in self.periodes.items():
            per = ET.SubElement(p_elem, "Periode", attrib={"option": opt})
            per.text = val
        h_elem = ET.SubElement(elem, "Horaires")
        for h in self.horaires:
            ET.SubElement(h_elem, "HoraireID").text = str(h.id if hasattr(h, 'id') else h)
        ET.SubElement(elem, "GroupesFixes").text = str(int(self.groupes_fixes))
        ET.SubElement(elem, "Places").text = str(self.places)
        ET.SubElement(elem, "AlternanceFixe").text = str(int(self.alternance_fixe))
        ET.SubElement(elem,"DecalageSemaines").text=str(int(self.decalage_semaines))
        return elem

    @staticmethod
    def from_xml(elem):
        id = elem.attrib["id"]
        nom = elem.find("Nom").text
        classe = elem.find("ClasseID").text
        periodes = {p.attrib["option"]: p.text for p in elem.find("Periodes").findall("Periode")}
        horaires = [h.text for h in elem.find("Horaires").findall("HoraireID")]
        groupes_fixes = bool(int(elem.find("GroupesFixes").text))
        places = int(elem.find("Places").text)
        alternance_fixe = bool(int(elem.find("AlternanceFixe").text))
        if elem.find("DecalageSemaines") is not None:
            decalage_semaines=int(elem.find("DecalageSemaines").text)
        else:
            decalage_semaines=0
        return TP(id, nom, classe, periodes, horaires, groupes_fixes, places, alternance_fixe,decalage_semaines)

    def resolve(self, db):
        self.classe = db["classes"][self.classe]
        self.horaires = [db["horaires"][h] for h in self.horaires]

# %% Définition de la classe "etudiant"

class etudiant:
    def __init__(self,id,nom,classe,groupe,options):
        self.id=id #Identifiant unique pour l'étudiant
        self.nom=nom # Nom et prénom de l'étudiant
        self.classe=classe #Classe de l'étudiant
        self.groupe=groupe #Numéro du groupe de colle de l'étudiant
        self.options=options #La liste des options de l'étudiant. Doit matcher le nom des options disponible dans la classe de l'étudiant.

    def to_xml(self):
        elem = ET.Element("Etudiant", attrib={"id": str(self.id)})
        ET.SubElement(elem, "Nom").text = self.nom
        ET.SubElement(elem, "ClasseID").text = str(self.classe.id if hasattr(self.classe, 'id') else self.classe)
        ET.SubElement(elem, "Groupe").text = str(self.groupe)
        o_elem = ET.SubElement(elem, "Options")
        for o in self.options:
            ET.SubElement(o_elem, "Option").text = o
        return elem

    @staticmethod
    def from_xml(elem):
        id = elem.attrib["id"]
        nom = elem.find("Nom").text
        classe = elem.find("ClasseID").text
        groupe = int(elem.find("Groupe").text)
        options = [o.text for o in elem.find("Options").findall("Option")]
        return etudiant(id, nom, classe, groupe, options)

    def resolve(self, db):
        self.classe = db["classes"][self.classe]

    def dispo_edt(self,horaire,semaine):
        """
        On vérifie dans l'edt de la classe de l'étudiant si l'horaire en entrée est disponible pour l'étudiant ou pas pour la semaine en entrée
        """
        if semaine not in horaire.semaines and not set(horaire.options).intersection(set(self.options)) : #Au cas où on n'a pas fait gaffe dans l'appel à la fonction (horaire non disponible de toutes façons cette semaine ou horaire ne matchant pas les options de l'étudiant)
            return False
        for h2 in self.classe.edt:
            if set(h2.options).intersection(set(self.options)): #On vérifie si les options matchent ou pas
                if horaire.overlap(h2,semaine): #On vérifie si il y a chevauchement cette semaine
                    return False
        return True

    def trouver_option(self,MT):
        """
        Renvoie l'option de l'etudiant dans la matiere/TP en entree, ou une chaine vide si elle n'existe pas
        """
        if set(self.options).intersection(MT.options):
            return list(set(self.options).intersection(MT.options))[0]
        else:
            return ''

# %% Définition de la classe "classe"

class classe:
    def __init__(self,id,nom,etudiants,matieres,TP,options,semaines_colles,semaines_cours,edt,matieres_groupees,nbCollesMax):
        self.id=id
        self.nom=nom #Le nom de la classe
        self.etudiants=etudiants #La liste des etudiants associes à la classe
        self.matieres=matieres #La liste des matieres associées a la classe
        self.TP=TP #La liste des TP associés à la classe
        self.options=options #La liste des options associées à la classe. Attention, la liste en entrée doit contenir au moins une option avec le nom de la classe pour des raisons de facilité de codage
        self.semaines_colles=semaines_colles # La liste ORDONNEE des semaines correspondantes du colloscope de la classe
        self.semaines_cours=semaines_cours #La liste ORDONNEE des semaines de cours pour la classe (contient semaines_colles a priori !)
        self.edt=edt #Une liste d'horaires qui correspond à l'edt de la classe. Les options sont gérées dans les horaires.
        self.matieres_groupees=matieres_groupees #Un dictionnaire dont les clés sont des couples  (uplets(matieres/TP),option) et les clés une liste d'entiers qui permet de connaître l'alternance désirée des matières/TP pour l'option en clés en fixant le debut de chaque periode. Normalement, le premier element de la liste est toujours 0.
        self.nbCollesMax=nbCollesMax #Le nombre de colles maximum par semaine pour un étudiant

    def to_xml(self):
        elem = ET.Element("Classe", attrib={"id": str(self.id)})
        ET.SubElement(elem, "Nom").text = self.nom
        e_elem = ET.SubElement(elem, "Etudiants")
        for e in self.etudiants:
            ET.SubElement(e_elem, "EtudiantID").text = str(e.id if hasattr(e, 'id') else e)
        m_elem = ET.SubElement(elem, "Matieres")
        for m in self.matieres:
            ET.SubElement(m_elem, "MatiereID").text = str(m.id if hasattr(m, 'id') else m)
        t_elem = ET.SubElement(elem, "TPs")
        for t in self.TP:
            ET.SubElement(t_elem, "TPID").text = str(t.id if hasattr(t, 'id') else t)
        o_elem = ET.SubElement(elem, "Options")
        for o in self.options:
            ET.SubElement(o_elem, "Option").text = o
        s_elem = ET.SubElement(elem, "SemainesColles")
        for s in self.semaines_colles:
            ET.SubElement(s_elem, "Semaine").text = str(s)
        sc_elem = ET.SubElement(elem, "SemainesCours")
        for s in self.semaines_cours:
            ET.SubElement(sc_elem, "Semaine").text = str(s)
        edt_elem = ET.SubElement(elem, "EDT")
        for h in self.edt:
            ET.SubElement(edt_elem, "HoraireID").text = str(h.id if hasattr(h, 'id') else h)
        mat_groupees_elem = ET.SubElement(elem, "MatieresGroupees")
        for (matieres_tuple, option), valeurs in self.matieres_groupees.items():
            group_elem = ET.SubElement(mat_groupees_elem, "Groupe")

            matieres_elem = ET.SubElement(group_elem, "Matieres")
            for matiere in matieres_tuple:
                ET.SubElement(matieres_elem, "Ref", attrib={"id": matiere.id})

            ET.SubElement(group_elem, "Option").text = option

            valeurs_elem = ET.SubElement(group_elem, "Valeurs")
            for v in valeurs:
                ET.SubElement(valeurs_elem, "Valeur").text = str(v)
        ET.SubElement(elem, "NbCollesMax").text = str(self.nbCollesMax)
        return elem

    @staticmethod
    def from_xml(elem):
        id = elem.attrib["id"]
        nom = elem.find("Nom").text
        etudiants = [e.text for e in elem.find("Etudiants").findall("EtudiantID")]
        matieres = [m.text for m in elem.find("Matieres").findall("MatiereID")]
        TP = [t.text for t in elem.find("TPs").findall("TPID")]
        options = [o.text for o in elem.find("Options").findall("Option")]
        semaines_colles = [int(s.text) for s in elem.find("SemainesColles").findall("Semaine")]
        semaines_cours = [int(s.text) for s in elem.find("SemainesCours").findall("Semaine")]
        edt = [h.text for h in elem.find("EDT").findall("HoraireID")]
        matieres_groupees = {}

        for group_elem in elem.find("MatieresGroupees").findall("Groupe"):
            matieres_ids = [ref.attrib["id"] for ref in group_elem.find("Matieres").findall("Ref")]
            option = group_elem.find("Option").text
            valeurs = tuple(int(v.text) for v in group_elem.find("Valeurs").findall("Valeur"))

            # on stocke les IDs pour résoudre plus tard
            matieres_groupees[(tuple(matieres_ids), option)] = valeurs
        nbCollesMax = int(elem.find("NbCollesMax").text)
        return classe(id, nom, etudiants, matieres, TP, options, semaines_colles, semaines_cours, edt, matieres_groupees, nbCollesMax)

    def resolve(self, db):
        self.etudiants = [db["etudiants"][e] for e in self.etudiants]
        self.matieres = [db["matieres"][m] for m in self.matieres]
        self.TP = [db["TPs"][t] for t in self.TP]
        self.edt = [db["horaires"][h] for h in self.edt]
        resolved = {}
        for (mat_ids, option), valeurs in self.matieres_groupees.items():
            matieres = tuple(db["matieres"][mid] for mid in mat_ids)
            resolved[(matieres, option)] = valeurs

        self.matieres_groupees = resolved


    def ppcm_periodes(self):
        """
        Renvoie un dictionnaire dont les entrées sont des tuples d'options possibles de la classe et les clés le ppcm des périodes des matières avec alternance fixe associées à ce tuple d'option
        """
        P={}
        for etudiant in self.etudiants: #On récupère les tuples d'options possibles
            if tuple(etudiant.options) not in P:
                P[tuple(etudiant.options)]=[]
        for matiere in self.matieres:
            if matiere.alternance_fixe:
                S=set(matiere.options)
                for key in P:
                    O=list(S.intersection(set(key)))
                    if O!=[]: # On vérifie pour chaque matiere si une option d'un tuple étudiant est présente dans la matière
                        P[key].append(len(matiere.periodes[O[0]]))
        for TP in self.TP:
            if TP.alternance_fixe:
                S=set(TP.options)
                for key in P:
                    O=list(S.intersection(set(key)))
                    if O!=[]: # On vérifie pour chaque TP si une option d'un tuple étudiant est présente dans le TP
                        P[key].append(len(TP.periodes[O[0]]))
        for key in P:
            P[key]=math.lcm(*P[key])
        return P

    def find_all_horaires(self):
        """
        Trouve tous les horaires de la classe
        """
        H=[]
        for matiere in self.matieres:
            for colleur in matiere.colleurs:
                H+=[h for h in colleur.horaires]
        for TP in self.TP:
            H+=[h for h in TP.horaires]
        return H

    def groupes_horaires_overlap(self):
        """
        Crée une liste de listes contenant les overlap possibles
        """
        H=self.find_all_horaires()
        Types=[]
        for h in H:
            if (h.jour,h.debut,h.duree) not in Types:
                Types.append((h.jour,h.debut,h.duree))
        Types=sorted(Types)
        f=lambda x,y :(x[0]==y[0]) and ( (x[1]<=y[1] and x[1]+x[2]>y[1]) or (y[1]<=x[1] and y[1]+y[2]>x[1]) )
        Groupes=[[]]
        for T in Types:
            if Groupes[-1]==[]:
                Groupes[-1].append(T)
            else:
                Adj=[]
                non_adj=[]
                for Y in Groupes[-1]:
                    if f(Y,T):
                        Adj.append(Y)
                    else:
                        non_adj.append(Y)
                if non_adj!=[]:
                    Groupes.append([A for A in Adj]+[T])
                else:
                    Groupes[-1].append(T)
        return [[h for h in H if (h.jour,h.debut,h.duree) in G] for G in Groupes]


# %% Calendrier

class Calendrier:
    def __init__(self, rentree, fin, vacances, jours_feries_manuel=None):
        self.rentree = rentree            # datetime.date
        self.fin = fin                    # datetime.date
        self.vacances = vacances          # dict nom → (date_debut, date_reprise)
        self.jours_feries_manuel = jours_feries_manuel or []
        self.jours_feries_auto = self.calculer_jours_feries()



    @property
    def jours_feries(self):
        return sorted(set(self.jours_feries_auto + self.jours_feries_manuel))

    def calculer_jours_feries(self):
        from datetime import date, timedelta
        from dateutil.easter import easter

        jours_feries = set()
        annee = self.rentree.year
        while annee <= self.fin.year:
            paques = easter(annee)
            lundi_paques = paques + timedelta(days=1)
            ascension = paques + timedelta(days=39)
            vendredi_ascension = ascension + timedelta(days=1)
            samedi_ascension = ascension + timedelta(days=2)
            lundi_pentecote = paques + timedelta(days=50)

            fériés = [
                date(annee, 1, 1),
                lundi_paques,
                date(annee, 5, 1),
                date(annee, 5, 8),
                ascension,
                vendredi_ascension,
                samedi_ascension,
                lundi_pentecote,
                date(annee, 7, 14),
                date(annee, 8, 15),
                date(annee, 11, 1),
                date(annee, 11, 11),
                date(annee, 12, 25),
            ]

            for jour in fériés:
                if self.rentree <= jour <= self.fin:
                    if not any(debut <= jour < reprise for debut, reprise in self.vacances.values()):
                        jours_feries.add(jour)
            annee += 1

        return sorted(jours_feries)


    def to_xml(self):
        from xml.etree.ElementTree import Element, SubElement

        elem = Element("Calendrier")
        SubElement(elem, "Rentree").text = self.rentree.isoformat()
        SubElement(elem, "Fin").text = self.fin.isoformat()

        for nom, (debut, reprise) in self.vacances.items():
            vac = SubElement(elem, "Vacances", attrib={"nom": nom})
            SubElement(vac, "Debut").text = debut.isoformat()
            SubElement(vac, "Reprise").text = reprise.isoformat()

        # Ajouter les jours fériés manuels uniquement (i.e. non calculés)
        jours_calcules = set(self.calculer_jours_feries())
        jours_manuel = set(self.jours_feries) - jours_calcules
        for jour in sorted(jours_manuel):
            SubElement(elem, "JourFerie").text = jour.isoformat()

        return elem


    @staticmethod
    def from_xml(elem):
        from datetime import date

        rentree = date.fromisoformat(elem.find("Rentree").text)
        fin = date.fromisoformat(elem.find("Fin").text)

        vacances = {}
        for vac in elem.findall("Vacances"):
            nom = vac.attrib["nom"]
            debut = date.fromisoformat(vac.find("Debut").text)
            reprise = date.fromisoformat(vac.find("Reprise").text)
            vacances[nom] = (debut, reprise)

        jours_feries_manuel = []
        for jf in elem.findall("JourFerie"):
            jours_feries_manuel.append(date.fromisoformat(jf.text))

        return Calendrier(rentree, fin, vacances, jours_feries_manuel)

    def semaine_to_dates(self, num_semaine):
        """
        Renvoie (début, fin) de la semaine n°num_semaine :
        - Semaine 1 commence à la date de rentrée, finit le samedi suivant (ou la fin de l’année si plus tôt).
        - Les semaines suivantes vont du lundi au samedi (ou jusqu'à la fin de l’année).
        - Ignore les vacances (hors samedi de début et lundi de reprise).
        - Soulève une erreur si la semaine n’existe pas avant la fin d’année.
        """
        def prochain_samedi(jour):
            jours_a_ajouter = (5 - jour.weekday()) % 7
            return jour + timedelta(days=jours_a_ajouter)



        # --- Semaine 1 ---
        debut = self.rentree
        fin = min(prochain_samedi(debut), self.fin)
        if num_semaine == 1:
            return (debut, fin)

        semaine_count = 1
        jour = fin + timedelta(days=1)
        # aligne sur lundi
        if jour.weekday() != 0:
            jour += timedelta(days=(7 - jour.weekday()))

        while jour <= self.fin:
            fin_semaine = min(jour + timedelta(days=5), self.fin)
            semaine_count += 1
            if semaine_count == num_semaine:
                return (jour, fin_semaine)
            jour += timedelta(days=7)

        raise ValueError(f"La semaine {num_semaine} dépasse la fin de l'année ({self.fin}).")

    def get_all_semaines(self):
        """
        Renvoie un dictionnaire de toutes les semaines de cours dont les valeurs sont les dates de fin et de départ
        """
        def est_semaine_de_vacances(lundi, samedi):
            for debut, reprise in self.vacances.values():
                vac_start = debut + timedelta(days=1)   # exclut samedi début
                vac_end = reprise - timedelta(days=1)   # exclut lundi reprise
                if vac_start <= samedi and vac_end >= lundi:
                    return True
            return False
        S={}
        i=1
        while True:
            try:
                s=self.semaine_to_dates(i)
                if not est_semaine_de_vacances(s[0],s[1]):
                    S[i]=s
                i+=1
            except:
                break
        return S

    def est_chome(self, jour, semaine):
        """
        Vérifie si le jour donné est chômé lors de la semaine spécifiée.
        - `jour` : str, parmi ['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi']
        - `semaine` : int, numéro de la semaine selon get_all_semaines()
        """

        # Dictionnaire jour -> offset dans la semaine
        jours_index = {
            "Lundi": 0,
            "Mardi": 1,
            "Mercredi": 2,
            "Jeudi": 3,
            "Vendredi": 4,
            "Samedi": 5
        }

        if semaine not in self.get_all_semaines():
            return False  # Semaine invalide

        debut_semaine, _ = self.get_all_semaines()[semaine]
        offset = jours_index.get(jour)
        if offset is None:
            return False  # Jour invalide

        date_cible = debut_semaine + timedelta(days=offset)
        return date_cible in self.jours_feries

    def get_date(self, semaine: int,jour: str):
        """
        Retourne la date correspondant à un jour ('lundi', 'mardi', ...)
        dans une semaine donnée (int), insensible à la casse.
        """
        dico_semaines = self.get_all_semaines()
        if semaine not in dico_semaines:
            raise ValueError(f"Semaine {semaine} non trouvée dans le calendrier.")

        date_debut = dico_semaines[semaine][0]

        JOURS_SEMAINE = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
        jour_normalise = jour.strip().lower()

        if jour_normalise not in JOURS_SEMAINE:
            raise ValueError(f"Jour invalide : {jour}")

        index_jour = JOURS_SEMAINE.index(jour_normalise)
        return date_debut + timedelta(days=index_jour)



# %% save/load functions

def save_all(db, filename):
    root = ET.Element("Donnees")
    for key in db.keys():
        if key!='calendrier':
            section = ET.SubElement(root, key.capitalize())
            for obj in db[key].values():
                section.append(obj.to_xml())
    if "calendrier" in db:
        if db['calendrier']is not None:
            root.append(db["calendrier"].to_xml())
    tree = ET.ElementTree(root)
    tree.write(filename, encoding="utf-8", xml_declaration=True)

def load_all(filename):
    tree = ET.parse(filename)
    root = tree.getroot()
    keys=["colleurs","horaires","matieres","TPs","etudiants","classes"]
    classes = {"colleurs": colleur, "horaires": horaire, "matieres": matiere,"TPs":TP,"etudiants":etudiant,"classes":classe}
    db = {key: {} for key in keys}

    for key in keys:
        section = root.find(key.capitalize())
        if section is not None:
            for elem in section:
                obj = classes[key].from_xml(elem)
                db[key][obj.id] = obj
    for key in keys:
        for obj in db[key].values():
            obj.resolve(db)
    if root.find("Calendrier") is not None:
        db["calendrier"] = Calendrier.from_xml(root.find("Calendrier"))
    return db



if __name__=='__main__':



    #Test mini TSI1+TSI2 + mini PCSI
    ID='0'
    #Définition des classes
    Classes=[]
    Classes.append(classe(ID,'TSI1',[],[],[],['TSI1'],[i for i in range(2,32)],[i for i in range(36)],[],{},3))
    ID=str(int(ID)+1)
    Classes.append(classe(ID,'PCSI',[],[],[],['PCSI','C','SI','I1','I2'],[i for i in range(2,17)],[i for i in range(17)],[],{},3))
    ID=str(int(ID)+1)
    Classes.append(classe(ID,'TSI2',[],[],[],['TSI2'],[i for i in range(2,24)],[i for i in range(25)],[],{},3))
    ID=str(int(ID)+1)
    #Ajout des étudiants
    TSI1=Classes[0]
    for i in range(5):
        for k in range(3):
            TSI1.etudiants.append(etudiant(ID,'etudiant_'+str(3*i+k),TSI1,i,['TSI1']))
            ID=str(int(ID)+1)
    PCSI=Classes[1]
    for i in range(5):
        for k in range(3):
            if i<3:
                PCSI.etudiants.append(etudiant(ID,'etudiant_'+str(3*i+k),PCSI,i,['PCSI','I1']))
                ID=str(int(ID)+1)
            else:
                PCSI.etudiants.append(etudiant(ID,'etudiant_'+str(3*i+k),PCSI,i,['PCSI','I2']))
                ID=str(int(ID)+1)
    TSI2=Classes[2]
    for i in range(7):
        for k in range(3):
            TSI2.etudiants.append(etudiant(ID,'etudiant_'+str(3*i+k),TSI2,i,['TSI2']))
            ID=str(int(ID)+1)

    #Ajout des matières
    TSI1.matieres.append(matiere(ID,'Maths',TSI1,{'TSI1':'1'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI1.matieres.append(matiere(ID,'Physique',TSI1,{'TSI1':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI1.matieres.append(matiere(ID,'Anglais',TSI1,{'TSI1':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI1.matieres.append(matiere(ID,'SIK',TSI1,{'TSI1':'1000'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI1.matieres.append(matiere(ID,'SIE',TSI1,{'TSI1':'1000'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI1.matieres.append(matiere(ID,'Francais',TSI1,{'TSI1':'1000000000'},3,30,30,False,[],1,False))
    ID=str(int(ID)+1)

    TSI2.matieres.append(matiere(ID,'Maths',TSI2,{'TSI2':'1'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI2.matieres.append(matiere(ID,'Physique',TSI2,{'TSI2':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI2.matieres.append(matiere(ID,'Anglais',TSI2,{'TSI2':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI2.matieres.append(matiere(ID,'SIK',TSI2,{'TSI2':'1000'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI2.matieres.append(matiere(ID,'SIE',TSI2,{'TSI2':'1000'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    TSI2.matieres.append(matiere(ID,'Francais',TSI2,{'TSI2':'1000000000'},2,30,30,False,[],1,False))
    ID=str(int(ID)+1)

    PCSI.matieres.append(matiere(ID,'Maths',PCSI,{'PCSI':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    PCSI.matieres.append(matiere(ID,'Physique',PCSI,{'PCSI':'10100100'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    PCSI.matieres.append(matiere(ID,'Anglais',PCSI,{'PCSI':'10'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    PCSI.matieres.append(matiere(ID,'SI',PCSI,{'PCSI':'1000'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    PCSI.matieres.append(matiere(ID,'Chimie',PCSI,{'PCSI':'10100100'},40,55,0,True,[],3,True))
    ID=str(int(ID)+1)
    PCSI.matieres.append(matiere(ID,'Francais',PCSI,{'PCSI':'1000000000'},3,30,30,False,[],1,False))
    ID=str(int(ID)+1)

    #Groupement de matieres en PCSI

    PCSI.matieres_groupees[((PCSI.matieres[0],PCSI.matieres[2]),'PCSI')]=[0,1]
    PCSI.matieres_groupees[((PCSI.matieres[1],PCSI.matieres[3],PCSI.matieres[4]),'PCSI')]=[0,1,4]

    #Ajout TP
    TSI1.TP.append(TP(ID,'TP_Info',TSI1,{'TSI1':'1'},[],False,5,True))
    ID=str(int(ID)+1)

    #Ajout TP info PCSI dans l'edt en fonction du groupe
    PCSI.edt.append(horaire(ID,'lundi',960,120,[2*i for i in range(1,9)],False,[],['I1'],3,None))
    ID=str(int(ID)+1)
    PCSI.edt.append(horaire(ID,'lundi',960,120,[2*i+1 for i in range(1,9)],False,[],['I2'],3,None))
    ID=str(int(ID)+1)

    #Ajout Colleurs
    for i in range(5):
        CL=colleur(ID,'colleur_maths_TSI_'+str(i),[],{TSI1.matieres[0] : 1,TSI2.matieres[0]:1})
        ID=str(int(ID)+1)
        TSI1.matieres[0].colleurs.append(CL)
        TSI2.matieres[0].colleurs.append(CL)
    CL=colleur(ID,'colleur_maths_TSI_'+str(i),[],{TSI2.matieres[0]:2})
    ID=str(int(ID)+1)
    TSI2.matieres[0].colleurs.append(CL)
    for i in range(4):
        if i in [0,1]:
            CL=colleur(ID,'colleur_phy_TSI_'+str(i),[],{TSI1.matieres[1]:1,TSI2.matieres[1]:1})
            ID=str(int(ID)+1)
            TSI1.matieres[1].colleurs.append(CL)
            TSI2.matieres[1].colleurs.append(CL)
        if i==2:
            CL=colleur(ID,'colleur_phy_TSI_'+str(i),[],{TSI1.matieres[1]:0.5,TSI2.matieres[1]:1})
            ID=str(int(ID)+1)
            TSI1.matieres[1].colleurs.append(CL)
            TSI2.matieres[1].colleurs.append(CL)
        if i==3:
            CL=colleur(ID,'colleur_phy_TSI_'+str(i),[],{TSI2.matieres[1]:0.5})
            ID=str(int(ID)+1)
            TSI2.matieres[1].colleurs.append(CL)

    for i in range(4):
        if i in [0,1]:
            CL=colleur(ID,'colleur_anglais_TSI_'+str(i),[],{TSI1.matieres[2]:1,TSI2.matieres[2]:1})
            ID=str(int(ID)+1)
            TSI1.matieres[2].colleurs.append(CL)
            TSI2.matieres[2].colleurs.append(CL)
        if i==2:
            CL=colleur(ID,'colleur_anglais_TSI_'+str(i),[],{TSI1.matieres[2]:0.5,TSI2.matieres[2]:1})
            ID=str(int(ID)+1)
            TSI1.matieres[2].colleurs.append(CL)
            TSI2.matieres[2].colleurs.append(CL)
        if i==3:
            CL=colleur(ID,'colleur_anglais_TSI_'+str(i),[],{TSI2.matieres[2]:0.5})
            ID=str(int(ID)+1)

            TSI2.matieres[2].colleurs.append(CL)

    TSI1.matieres[3].colleurs.append(colleur(ID,'colleur_SIK_TSI1',[],{TSI1.matieres[3]:1}))
    ID=str(int(ID)+1)
    TSI2.matieres[3].colleurs.append(colleur(ID,'colleur_SIK_TSI2_0',[],{TSI2.matieres[3]:1.75}))
    ID=str(int(ID)+1)
    TSI1.matieres[3].colleurs.append(colleur(ID,'colleur_SIK_TSI1_1',[],{TSI1.matieres[3]:0.25}))
    ID=str(int(ID)+1)
    TSI2.matieres[4].colleurs.append(colleur(ID,'colleur_SIE_TSI2',[],{TSI2.matieres[4]:1.75}))
    ID=str(int(ID)+1)
    TSI1.matieres[4].colleurs.append(colleur(ID,'colleur_SIE_TSI1_0',[],{TSI1.matieres[4]:1}))
    ID=str(int(ID)+1)
    TSI1.matieres[4].colleurs.append(colleur(ID,'colleur_SIE_TSI1_1',[],{TSI1.matieres[4]:0.25}))
    ID=str(int(ID)+1)
    CLF=colleur(ID,'colleur_francais_TSI',[],{TSI1.matieres[5]:3,TSI2.matieres[5]:3})
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs.append(CLF)
    TSI2.matieres[5].colleurs.append(CLF)
    PCSI.matieres[0].colleurs.append(colleur(ID,'colleur_M_PCSI',[],{PCSI.matieres[0]:2.5}))
    ID=str(int(ID)+1)
    PCSI.matieres[1].colleurs.append(colleur(ID,'colleur_P_PCSI',[],{PCSI.matieres[1]:1.875}))
    ID=str(int(ID)+1)
    PCSI.matieres[2].colleurs.append(colleur(ID,'colleur_A_PCSI',[],{PCSI.matieres[2]:2.5}))
    ID=str(int(ID)+1)
    PCSI.matieres[3].colleurs.append(colleur(ID,'colleur_SI_PCSI',[],{PCSI.matieres[3]:1.25}))
    ID=str(int(ID)+1)
    PCSI.matieres[4].colleurs.append(colleur(ID,'colleur_C_PCSI',[],{PCSI.matieres[4]:1.875}))
    ID=str(int(ID)+1)
    PCSI.matieres[5].colleurs.append(colleur(ID,'colleur_F_PCSI',[],{PCSI.matieres[5]:3}))
    ID=str(int(ID)+1)


    #Horaires Maths
    ColleursMTSI=[colleur for colleur in TSI2.matieres[0].colleurs]
    for i in range(5):
        ColleursMTSI[i].horaires.append(horaire(ID,'mercredi',840,55,[i for i in range(2,32)],False,[TSI1.matieres[0],TSI2.matieres[0]],['TSI1','TSI2'],3,ColleursMTSI[i]))
        ID=str(int(ID)+1)
        ColleursMTSI[i].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,24)],False,[TSI1.matieres[0],TSI2.matieres[0]],['TSI1','TSI2'],3,ColleursMTSI[i]))
        ID=str(int(ID)+1)
    ColleursMTSI[5].horaires.append(horaire(ID,'lundi',960,55,[i for i in range(2,24)],False,[TSI2.matieres[0]],['TSI2'],3,ColleursMTSI[5]))
    ID=str(int(ID)+1)
    ColleursMTSI[5].horaires.append(horaire(ID,'lundi',900,55,[i for i in range(2,24)],False,[TSI2.matieres[0]],['TSI2'],3,ColleursMTSI[5]))
    ID=str(int(ID)+1)

    PCSI.matieres[0].colleurs[0].horaires.append(horaire(ID,'lundi',960,55,[i for i in range(2,17)],False,[PCSI.matieres[0]],['PCSI'],3,PCSI.matieres[0].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[0].colleurs[0].horaires.append(horaire(ID,'lundi',1020,55,[i for i in range(2,17)],False,[PCSI.matieres[0]],['PCSI'],3,PCSI.matieres[0].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[0].colleurs[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,17)],True,[PCSI.matieres[0]],['PCSI'],3,PCSI.matieres[0].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires Physique
    TSI1.matieres[1].colleurs[0].horaires.append(horaire(ID,'mercredi',1020,55,[i for i in range(2,32)],False,[TSI1.matieres[1],TSI2.matieres[1]],['TSI1','TSI2'],3,TSI1.matieres[1].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[1].colleurs[0].horaires.append(horaire(ID,'jeudi',960,55,[i for i in range(2,24)],False,[TSI1.matieres[1],TSI2.matieres[1]],['TSI1','TSI2'],3,TSI1.matieres[1].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[1].colleurs[1].horaires.append(horaire(ID,'jeudi',960,55,[i for i in range(2,32)],False,[TSI1.matieres[1],TSI2.matieres[1]],['TSI1','TSI2'],3,TSI1.matieres[1].colleurs[1]))
    ID=str(int(ID)+1)
    TSI1.matieres[1].colleurs[1].horaires.append(horaire(ID,'jeudi',1020,55,[i for i in range(2,24)],False,[TSI1.matieres[1],TSI2.matieres[1]],['TSI1','TSI2'],3,TSI1.matieres[1].colleurs[1]))
    ID=str(int(ID)+1)
    TSI1.matieres[1].colleurs[2].horaires.append(horaire(ID,'vendredi',1020,55,[i for i in range(2,32)],True,[TSI1.matieres[1]],['TSI1'],3,TSI1.matieres[1].colleurs[2]))
    ID=str(int(ID)+1)
    TSI1.matieres[1].colleurs[2].horaires.append(horaire(ID,'lundi',1020,55,[i for i in range(2,24)],False,[TSI1.matieres[1],TSI2.matieres[1]],['TSI1','TSI2'],3,TSI1.matieres[1].colleurs[2]))
    ID=str(int(ID)+1)
    TSI2.matieres[1].colleurs[3].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],True,[TSI2.matieres[1]],['TSI2'],3,TSI2.matieres[1].colleurs[3]))
    ID=str(int(ID)+1)

    PCSI.matieres[1].colleurs[0].horaires.append(horaire(ID,'vendredi',960,55,[i for i in range(2,17)],False,[PCSI.matieres[1]],['PCSI'],3,PCSI.matieres[1].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[1].colleurs[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,17)],True,[PCSI.matieres[1]],['PCSI'],3,PCSI.matieres[1].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires Anglais
    TSI1.matieres[2].colleurs[0].horaires.append(horaire(ID,'vendredi',960,55,[i for i in range(2,32)],False,[TSI1.matieres[2],TSI2.matieres[2]],['TSI1','TSI2'],3,TSI1.matieres[2].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[2].colleurs[0].horaires.append(horaire(ID,'vendredi',1020,55,[i for i in range(2,24)],False,[TSI1.matieres[2],TSI2.matieres[2]],['TSI1','TSI2'],3,TSI1.matieres[2].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[2].colleurs[1].horaires.append(horaire(ID,'mardi',960,55,[i for i in range(2,32)],False,[TSI1.matieres[2],TSI2.matieres[2]],['TSI1','TSI2'],3,TSI1.matieres[2].colleurs[1]))
    ID=str(int(ID)+1)
    TSI1.matieres[2].colleurs[1].horaires.append(horaire(ID,'mardi',1020,55,[i for i in range(2,24)],False,[TSI1.matieres[2],TSI2.matieres[2]],['TSI1','TSI2'],3,TSI1.matieres[2].colleurs[1]))
    ID=str(int(ID)+1)
    TSI1.matieres[2].colleurs[2].horaires.append(horaire(ID,'vendredi',1020,55,[i for i in range(2,32)],True,[TSI1.matieres[2]],['TSI1'],3,TSI1.matieres[2].colleurs[2]))
    ID=str(int(ID)+1)
    TSI1.matieres[2].colleurs[2].horaires.append(horaire(ID,'lundi',1020,55,[i for i in range(2,24)],False,[TSI1.matieres[2],TSI2.matieres[2]],['TSI1','TSI2'],3,TSI1.matieres[2].colleurs[2]))
    ID=str(int(ID)+1)
    TSI2.matieres[2].colleurs[3].horaires.append(horaire(ID,'mercredi',1020,55,[i for i in range(2,32)],True,[TSI2.matieres[2]],['TSI2'],3,TSI2.matieres[2].colleurs[3]))
    ID=str(int(ID)+1)

    PCSI.matieres[2].colleurs[0].horaires.append(horaire(ID,'vendredi',1020,55,[i for i in range(2,17)],False,[PCSI.matieres[2]],['PCSI'],3,PCSI.matieres[2].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[2].colleurs[0].horaires.append(horaire(ID,'lundi',960,55,[i for i in range(2,17)],True,[PCSI.matieres[2]],['PCSI'],3,PCSI.matieres[2].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[2].colleurs[0].horaires.append(horaire(ID,'jeudi',960,55,[i for i in range(2,17)],True,[PCSI.matieres[2]],['PCSI'],3,PCSI.matieres[2].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires SI
    TSI1.matieres[3].colleurs[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,32)],False,[TSI1.matieres[3]],['TSI1'],3,TSI1.matieres[3].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[3].colleurs[1].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],True,[TSI1.matieres[3]],['TSI1'],3,TSI1.matieres[3].colleurs[1]))
    ID=str(int(ID)+1)
    TSI2.matieres[3].colleurs[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,32)],False,[TSI2.matieres[3]],['TSI2'],3,TSI1.matieres[3].colleurs[0]))
    ID=str(int(ID)+1)
    TSI2.matieres[3].colleurs[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],True,[TSI2.matieres[3]],['TSI2'],3,TSI2.matieres[3].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[4].colleurs[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,32)],False,[TSI1.matieres[4]],['TSI1'],3,TSI1.matieres[4].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[4].colleurs[1].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],True,[TSI1.matieres[4]],['TSI1'],3,TSI1.matieres[4].colleurs[1]))
    ID=str(int(ID)+1)
    TSI2.matieres[4].colleurs[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,32)],False,[TSI2.matieres[4]],['TSI2'],3,TSI2.matieres[4].colleurs[0]))
    ID=str(int(ID)+1)
    TSI2.matieres[4].colleurs[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],True,[TSI2.matieres[4]],['TSI2'],3,TSI2.matieres[4].colleurs[0]))
    ID=str(int(ID)+1)

    PCSI.matieres[3].colleurs[0].horaires.append(horaire(ID,'vendredi',960,55,[i for i in range(2,17)],True,[PCSI.matieres[3]],['PCSI'],3,PCSI.matieres[3].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[3].colleurs[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,17)],False,[PCSI.matieres[3]],['PCSI'],3,PCSI.matieres[3].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires Chimie

    PCSI.matieres[4].colleurs[0].horaires.append(horaire(ID,'vendredi',960,55,[i for i in range(2,17)],False,[PCSI.matieres[4]],['PCSI'],3,PCSI.matieres[4].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[4].colleurs[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,17)],True,[PCSI.matieres[4]],['PCSI'],3,PCSI.matieres[4].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires Français

    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',900,60,[i for i in range(2,32)],False,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',930,60,[i for i in range(2,32)],False,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',960,60,[i for i in range(2,32)],False,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'lundi',960,60,[i for i in range(2,32)],True,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'lundi',990,60,[i for i in range(2,32)],True,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    TSI1.matieres[5].colleurs[0].horaires.append(horaire(ID,'lundi',1020,60,[i for i in range(2,32)],True,[TSI1.matieres[5],TSI2.matieres[5]],['TSI1','TSI2'],1,TSI1.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)


    PCSI.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',900,60,[i for i in range(2,17)],True,[PCSI.matieres[5]],['PCSI'],1,PCSI.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',930,60,[i for i in range(2,17)],True,[PCSI.matieres[5]],['PCSI'],1,PCSI.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)
    PCSI.matieres[5].colleurs[0].horaires.append(horaire(ID,'mercredi',960,60,[i for i in range(2,17)],True,[PCSI.matieres[5]],['PCSI'],1,PCSI.matieres[5].colleurs[0]))
    ID=str(int(ID)+1)

    #Horaires TP

    TSI1.TP[0].horaires.append(horaire(ID,'mercredi',840,55,[i for i in range(2,32)],False,[TSI1.TP[0]],['TSI1'],5,None))
    ID=str(int(ID)+1)
    TSI1.TP[0].horaires.append(horaire(ID,'mercredi',900,55,[i for i in range(2,32)],False,[TSI1.TP[0]],['TSI1'],5,None))
    ID=str(int(ID)+1)
    TSI1.TP[0].horaires.append(horaire(ID,'mercredi',960,55,[i for i in range(2,32)],False,[TSI1.TP[0]],['TSI1'],5,None))
    ID=str(int(ID)+1)


    Colleurs=[]
    for C in Classes:
        for m in C.matieres:
            Colleurs+=m.colleurs
    Colleurs=list(set(Colleurs))
    TPS=[]
    for C in Classes:
        TPS+=C.TP
    Horaires=[]
    for CL in Colleurs:
        Horaires+=CL.horaires
    for T in TPS:
        Horaires+=T.horaires
    for C in Classes:
        Horaires+=C.edt
    Matieres=[]
    for C in Classes:
        Matieres+=C.matieres
    Etudiants=[]
    for C in Classes:
        Etudiants+=C.etudiants

    keys=["colleurs","horaires","matieres","TPs","etudiants","classes"]
    db = {key: {} for key in keys}
    for CL in Colleurs:
        db["colleurs"][CL.id]=CL
    for C in Classes:
        db["classes"][C.id]=C
    for h in Horaires:
        db["horaires"][h.id]=h
    for m in Matieres:
        db["matieres"][m.id]=m
    for T in TPS:
        db['TPs'][T.id]=T
    for e in Etudiants:
        db['etudiants'][e.id]=e

    db["calendrier"] = Calendrier(
        rentree=date(2025, 9, 1),
        fin=date(2026, 6, 25),
        vacances={
            "Toussaint": (date(2025, 10, 18), date(2025, 11, 3)),
            "Noël": (date(2025, 12, 20), date(2026, 1, 5)),
            "Hiver": (date(2026, 2, 14),date(2026, 3, 2)),
            "Printemps": (date(2026, 4, 11),date(2026, 4, 27)),
        }
    )

    save_all(db,"Test.xml")
    db=load_all('Test.xml')