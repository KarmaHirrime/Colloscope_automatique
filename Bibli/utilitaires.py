
def find_paths_through_key(D, k):
    """
    Renvoie tous les chemins [t1,...,tn,b1,...,bp]
    tels que le chemin complet D[t1]...[tn][k][b1]...[bp] est valide
    et aboutit à une valeur non dictionnaire.
    """
    results = []

    def dfs(d, path_before_k):
        if isinstance(d, dict):
            for key, val in d.items():
                if key == k:
                    # on entre dans le sous-dico k : explorer sans ajouter k au chemin
                    dfs_inside_k(val, path_before_k)
                else:
                    dfs(val, path_before_k + [key])

    def dfs_inside_k(d, path_after_k):
        if isinstance(d, dict):
            for key, val in d.items():
                dfs_inside_k(val, path_after_k + [key])
        else:
            results.append(path_after_k)

    dfs(D, [])
    return results

def intersection_of_multiple_lists(*lists):
    """
    Prend plusieurs listes de listes et retourne l'intersection :
    Tous les sous-listes identiques présentes dans TOUTES les listes.
    """
    if not lists:
        return []
    # Convertir chaque liste de listes en set de tuples
    sets_of_tuples = [set(tuple(x) for x in L) for L in lists]
    # Intersecter tous les sets
    common_tuples = set.intersection(*sets_of_tuples)
    # Reconvertir en liste de listes
    return [list(x) for x in common_tuples]



def cliques_maximales(L, f):
    from itertools import combinations

    # Création du graphe d'adjacence : voisinage selon f
    voisinage = {x: {y for y in L if x != y and f(x, y)} for x in L}

    resultats = []

    def bron_kerbosch(R, P, X):
        print(len(P),len(X))
        if not P and not X:
            resultats.append(list(R))
            return
        for v in list(P):
            bron_kerbosch(R | {v}, P & voisinage[v], X & voisinage[v])
            P.remove(v)
            X.add(v)

    bron_kerbosch(set(), set(L), set())
    return resultats

def ecarts(a,b):
    """
    Renvoie toutes les valeurs max telles
    """
    a1=int(a)
    b1=int(b)
    if b1==0:
        return[(2,1)]
    prod=0
    i=1
    L=[]
    while (prod+a1)%b1!=0:
        m=max([x for x in range(a1*b1) if a1*x//b1<i])
        L.append((m,i))
        prod=a1*m
        i+=1
    L.append((b1,a1))
    return L

def repete_chaine(c, start, l):
    """
    Renvoie une chaîne construite en répétant c à partir de l'indice start,
    puis en répétant c autant que nécessaire pour atteindre la longueur l.
    La dernière répétition est tronquée si nécessaire pour avoir une chaîne de longueur exactement l.
    """
    if not c or l <= 0 or start >= len(c):
        return ''

    # Commencer avec la fin de la première chaîne à partir de start
    resultat = c[start:]

    # Répéter c jusqu'à atteindre ou dépasser la longueur souhaitée
    while len(resultat) < l:
        resultat += c

    # Tronquer à la longueur exacte
    return resultat[:l]

def indices_uns_consecutifs(c, k):
    """
    Prend en entrée une chaîne de 0 et 1, et un entier k.
    Renvoie une liste de listes contenant les indices des k '1' consécutifs.
    Si k est trop grand (plus de '1' disponibles), renvoie une liste vide.
    """
    if k <= 0:
        return []

    # Trouver tous les indices où c[i] == '1'
    indices_uns = [i for i, char in enumerate(c) if char == '1']

    # Si pas assez de '1' pour faire un groupe de k, on renvoie []
    if len(indices_uns) < k:
        return []

    # Créer les sous-listes de k indices consécutifs
    resultats = [indices_uns[i:i+k] for i in range(len(indices_uns) - k + 1)]

    return resultats

def semaines_scores_ecarts(periode,poids,somme_poids,nb_semaines):
    """
    Permet de renvoyer un dictionnaire donc les clés sont les débuts possibles de la période, et les valeurs un autre dictionnaire dont les clés sont les couples renvoyés par la fonction écarts et les valeurs une liste de liste dont chaque élément contient l'indice des semaines à considérer pour les variables d'écarts
    """
    D={}
    EC=ecarts(poids,somme_poids)
    for start in range(len(periode)):
        D[start]={}
        newp=repete_chaine(periode,start,nb_semaines)
        for ec in EC:
            D[start][ec]=indices_uns_consecutifs(newp,ec[0])
    return D

def filtre_semaine_scores_ecarts(D,nb_semaines_previous):
    """
    Filtre les éléments du dictionnaire renvoyé par la fonction précédente, en ne gardant que les listes dont l'intersection avec semaines_previous et semaines_next est non vide
    """
    newD={}
    for start in D:
        newD[start]={}
        for couple in D[start]:
            newD[start][couple]=[el for el in D[start][couple] if min(el)<nb_semaines_previous and max(el)>=nb_semaines_previous]
    return newD


if __name__=='__main__':

    D = {
        "a": {
            1: {"x":4, "y":5, "z":6},
            2: {"y":4, "z":5},
            3: {"x","y","z"}
        },
        "b": {
            1: {"y":4, "z":5, "w":6},
            2: {"z":4, "x":5},
            3:{"x","y","z"}
        },
        "c":{
            1:{"x":4,"z":5},
            2:{"y":4,"w":5},
            3:{}
        },
        "d":{
            1:{"x":4,"y":5},
            3:{"y","z"}
        }
    }
    print(find_paths_through_key(D["a"],"y"))
    print(find_paths_through_key(D,"x"))
    Fx=find_paths_through_key(D,"x")
    Fy=find_paths_through_key(D,"y")
    print(intersection_of_multiple_lists(Fx,Fy))
    F1=find_paths_through_key(D,1)
    F2=find_paths_through_key(D,2)
    print(intersection_of_multiple_lists(F1,F2))
    Fa=find_paths_through_key(D,"a")
    Fc=find_paths_through_key(D,"c")
    print(intersection_of_multiple_lists(Fa,Fc))
    print(find_paths_through_key(D,4))
    x1=1
    x2=2
    x3=3
    x4=4

    L = [x1, x2, x3, x4]

    def f(x, y):
        return (x, y) in [(x1, x2), (x2, x3), (x2, x4), (x3, x4)] or (y, x) in [(x1, x2), (x2, x3), (x2, x4), (x3, x4)]

    print(cliques_maximales(L, f))

    print(ecarts(3,7))
    print(ecarts(1,4))
    print(ecarts(2,5))
    print(repete_chaine('10100100',2,30))
    c='101001010100101'
    print(indices_uns_consecutifs(c,2))
    print(indices_uns_consecutifs(c,3))
    print(indices_uns_consecutifs(c,5))
    c='10100100'
    E=semaines_scores_ecarts(c,2,5,17)
    print(E)
    newE=filtre_semaine_scores_ecarts(E,8)
    print(newE)
