import gurobipy as gp
from gurobipy import GRB
from classesColloscopeAuto import *
import utilitaires as ut
import math
import xml.etree.ElementTree as ET


# %% Creation du modele et des variables

def creer_modele(nom):
    return gp.Model(nom)

def ajout_variables_colles(semaine,classe,model,Variables):
    """
    Crée toutes les variables etudiants/colleurs correspondant à la semaine en entrée (type int) et à la classe en entrée (type "classe" définie dans le fichier des classes Pythons associées au programme) et les ajoute au modèle Gurobi.
    Les variables sont stockées dans le dictionnaire Variables qui contient toutes les variables du modèle Gurobi
    """
    if semaine not in Variables:
        Variables[semaine]={}
    for etudiant in classe.etudiants:
        if etudiant not in Variables[semaine]:
            Variables[semaine][etudiant]={}
        for matiere in classe.matieres:
            if set(matiere.options).intersection(set(etudiant.options)): #On vérifie si une option correspond
                if matiere not in  Variables[semaine][etudiant]:
                    Variables[semaine][etudiant][matiere]={}
                for colleur in matiere.colleurs:
                    if colleur not in Variables[semaine][etudiant][matiere]:
                        Variables[semaine][etudiant][matiere][colleur]={}
                    for i,horaire in enumerate(colleur.horaires):
                        if matiere in horaire.matieres and semaine in horaire.semaines and set(horaire.options).intersection(set(etudiant.options)) and etudiant.dispo_edt(horaire,semaine): #On vérifie si la matière est présente dans la liste correspondante pour l'horaire, si l'horaire est bien disponible cette semaine, si les options matchent et si l'horaire est disponible dans l'edt de l'étudiant
                            var_name="x_"+"S"+str(semaine)+"_"+etudiant.nom+"_"+colleur.nom+"_"+"horaire["+str(i)+"]"
                            Variables[semaine][etudiant][matiere][colleur][horaire]=model.addVar(vtype=GRB.BINARY, name=var_name)


def ajout_variables_TP(semaine,classe,model,Variables):
    """
    Crée les variables étudiants/TP correspondant à la semaine en entrée et à la classe en entrée, les ajoute au modèle Gurobi et stocke les variables dans le dictionnaire Variables
    """
    if semaine not in Variables:
        Variables[semaine]={}
    for etudiant in classe.etudiants:
        if etudiant not in Variables[semaine]:
            Variables[semaine][etudiant]={}
        for TP in classe.TP:
            if TP not in Variables[semaine]:
                Variables[semaine][etudiant][TP]={}
            if set(TP.options).intersection(set(etudiant.options)): #On vérifie si une option correspond
                for i,horaire in enumerate(TP.horaires):
                    if semaine in horaire.semaines and set(horaire.options).intersection(set(etudiant.options)) and etudiant.dispo_edt(horaire,semaine):
                        var_name="x_"+"S"+str(semaine)+"_"+etudiant.nom+"_"+TP.nom+"_"+"horaire["+str(i)+"]"
                        Variables[semaine][etudiant][TP][horaire]=model.addVar(vtype=GRB.BINARY,name=var_name)


def ajout_variables_auxiliaires_debut_periode(model,Variables_aux,Classes):
    """
    Crée les variables logiques auxiliaires utilisées dans les équations pour l'alternance des matieres
    """
    for classe in Classes:
        if classe not in Variables_aux:
            Variables_aux[classe]={}
            PP=classe.ppcm_periodes() #On récupère le dictionnaire tuples d'options/ppcm des périodes
            Variables_aux[classe]["fixe"]={}
            for key in PP:
                Variables_aux[classe]["fixe"][key]={}
                for matiere in classe.matieres:
                    if matiere.alternance_fixe:
                        S=set(matiere.options)
                        O=list(S.intersection(key))
                        if O!=[]: #Si une option de la clé est présente dans la matière
                            Variables_aux[classe]["fixe"][key][matiere]=[]
                            opt=O[0] #On récupère l'option
                            periode=matiere.periodes[opt] #on récupère la période correspondante
                            for k in range(len(periode)): #On crée autant de variables booléennes que la longueur de la période, représentant le début de la période de la matière dans le groupement des matières
                                var_name="x_"+classe.nom+"_"+matiere.nom+"_debut_periode_"+str(k)
                                Variables_aux[classe]["fixe"][key][matiere].append(model.addVar(vtype=GRB.BINARY,name=var_name))
                for TP in classe.TP:
                    if TP.alternance_fixe:
                        S=set(TP.options)
                        O=list(S.intersection(key))
                        if O!=[]: #Si une option de la clé est présente dans le TP
                            Variables_aux[classe]["fixe"][key][TP]=[]
                            opt=O[0] #On récupère l'option
                            periode=TP.periodes[opt] #on récupère la période correspondante
                            for k in range(len(periode)): #On crée autant de variables booléennes que la longueur de la période, représentant le début de la période du TP dans le groupement des matières
                                var_name="x_"+classe.nom+"_"+TP.nom+"_debut_periode_"+str(k)
                                Variables_aux[classe]["fixe"][key][TP].append(model.addVar(vtype=GRB.BINARY,name=var_name))
            for etudiant in classe.etudiants:
                Variables_aux[classe][etudiant]={}
                Variables_aux[classe][etudiant]["debut_periode"]={}
                Variables_aux[classe][etudiant]["debut_periode"]["fixe"]=[]
                for k in range(PP[tuple(etudiant.options)]): #On crée autant de variables booléennes que le ppcm des longueurs des périodes des matieres/TP avec alternance_fixe, représentant le début de la période pour l'étudiant
                    var_name="x_"+classe.nom+"_"+etudiant.nom+"_debut_periode_fixe_"+str(k)
                    Variables_aux[classe][etudiant]["debut_periode"]['fixe'].append(model.addVar(vtype=GRB.BINARY,name=var_name))
                Matieres_non_fixe=[matiere for matiere in classe.matieres if not matiere.alternance_fixe]
                Matieres_non_fixe+=[TP for TP in classe.TP if not TP.alternance_fixe]
                Variables_aux[classe][etudiant]["debut_periode"]['flexible']={}
                for matiere in Matieres_non_fixe:
                    if set(etudiant.options).intersection(matiere.options): #Si l'étudiant est concerné par la matière ou le TP
                        o=list(set(etudiant.options).intersection(matiere.options))[0]
                        Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]=[]
                        for k in range(len(matiere.periodes[o])): #On crée autant de variables que la longueur de la periode
                            var_name="x_"+classe.nom+"_"+etudiant.nom+"_debut_periode_"+matiere.nom+'_'+str(k)
                            Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere].append(model.addVar(vtype=GRB.BINARY,name=var_name))

                for semaine in classe.semaines_colles: #On ajoute les variables intermediaires de "somme de colles" qui seront egales a la somme des variables pour un semaine/etudiant/matiere ou TP donnés
                    Variables_aux[classe][etudiant][semaine]={}
                    for matiere in classe.matieres:
                        if set(matiere.options).intersection(set(etudiant.options)):
                            var_name="S_"+classe.nom+"_"+etudiant.nom+"_"+matiere.nom+"_semaine_"+str(semaine)
                            Variables_aux[classe][etudiant][semaine][matiere]=model.addVar(vtype=GRB.BINARY,name=var_name)
                    for TP in classe.TP:
                        if set(TP.options).intersection(set(etudiant.options)):
                            var_name="S_"+classe.nom+"_"+etudiant.nom+"_"+TP.nom+"_semaine_"+str(semaine)
                            Variables_aux[classe][etudiant][semaine][TP]=model.addVar(vtype=GRB.BINARY,name=var_name)

def ajout_variables_auxiliaires_occupation_creneaux(model,Variables_aux,Colleurs):
    """
    ajoute les variables d'occupation de créneaux (au moins un élève présent) pour chaque semaine de chaque horaire de chaque colleur
    prend en entrée la liste de tous les colleurs
    """
    Variables_aux["occupation_creneaux"]={}
    for colleur in Colleurs:
        if colleur not in Variables_aux["occupation_creneaux"]:
            Variables_aux["occupation_creneaux"][colleur]={}
        for matiere in colleur.matieres:
            Variables_aux["occupation_creneaux"][colleur][matiere]={}
            for i,horaire in enumerate(colleur.horaires):
                if matiere in horaire.matieres and horaire not in Variables_aux["occupation_creneaux"][colleur][matiere]:
                    Variables_aux["occupation_creneaux"][colleur][matiere][horaire]={}
                    for semaine in horaire.semaines:
                        if semaine not in Variables_aux["occupation_creneaux"][colleur][matiere][horaire] and semaine in matiere.classe.semaines_colles:
                            var_name="x_occupation_"+colleur.nom+"_horaire_"+str(i)+"_semaine_"+str(semaine)+'_'+matiere.classe.nom
                            Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine]=model.addVar(vtype=GRB.BINARY,name=var_name)






def ajout_variables_score(model,Variables_score,Classes):
    """
    Permet d'ajouter les variables necessaires au calcul du score pour le modele.
    """
    Variables_score["somme"]={}
    Variables_score["ecarts"]={}
    for classe in Classes:
        nb_semaines=len(classe.semaines_colles)
        for etudiant in classe.etudiants:
            Variables_score["ecarts"][etudiant]={}
            Variables_score["somme"][etudiant]={}
            for matiere in classe.matieres:
                if set(matiere.options).intersection(set(etudiant.options)) and len(matiere.colleurs)>1:
                    opt=list(set(matiere.options).intersection(set(etudiant.options)))[0] #On récupère l'option
                    somme_poids=sum([colleur.heures[matiere] for colleur in matiere.colleurs])
                    if int(somme_poids)==somme_poids: #S'il n'y a pas d'heures non entières
                        for colleur in matiere.colleurs:
                            Variables_score["ecarts"][etudiant][colleur]={}
                            Variables_score["somme"][etudiant][colleur]={}
                            Variables_score["somme"][etudiant][colleur]['tot']=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_somme_'+etudiant.nom+'_'+colleur.nom)
                            EC=ut.ecarts(colleur.heures[matiere],somme_poids)#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],colleur.heures[matiere],somme_poids,nb_semaines)

                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts"][etudiant][colleur][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts"][etudiant][colleur][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_'+str(couple[0])+'semaines_depart_'+str(depart))
                    else:
                        for colleur in matiere.colleurs:
                            Variables_score["somme"][etudiant][colleur]={}
                            Variables_score["somme"][etudiant][colleur]['tot']=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_somme_'+etudiant.nom+'_'+colleur.nom)
                            Variables_score["somme"][etudiant][colleur]['up']=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_somme_up'+etudiant.nom+'_'+colleur.nom)
                            Variables_score["somme"][etudiant][colleur]['down']=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_somme_down'+etudiant.nom+'_'+colleur.nom)
                            Variables_score["somme"][etudiant][colleur]['choix']=model.addVar(vtype=GRB.BINARY,name='x_choix_up_down_'+etudiant.nom+'_'+colleur.nom)
                            Variables_score["ecarts"][etudiant][colleur]={}
                            Variables_score["ecarts"][etudiant][colleur]["down"]={} #Cas où l'heure flexible saute pour l'étudiant à cause de son profil d'alternance de matières
                            EC=ut.ecarts(int(colleur.heures[matiere]),int(somme_poids))#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],int(colleur.heures[matiere]),int(somme_poids),nb_semaines)
                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts"][etudiant][colleur]["down"][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts"][etudiant][colleur]["down"][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_down_'+str(couple[0])+'semaines_depart_'+str(depart))
                            Variables_score["ecarts"][etudiant][colleur]["up"]={} #Cas où l'heure flexible existe pour l'étudiant
                            if int(colleur.heures[matiere])==colleur.heures[matiere]:
                                h=colleur.heures[matiere]
                            else:
                                h=int(colleur.heures[matiere])+1
                            EC=ut.ecarts(h,int(somme_poids)+1)#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],h,int(somme_poids)+1,nb_semaines)
                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts"][etudiant][colleur]["up"][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts"][etudiant][colleur]["up"][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_up_'+str(couple[0])+'semaines_depart_'+str(depart))
    Obj=[]
    for etudiant in Variables_score["somme"]:
        Obj+=[Variables_score['somme'][etudiant][colleur]['tot'] for colleur in Variables_score['somme'][etudiant]]
    if "periode_raccordement" in Variables_score:
        for etudiant in Variables_score["periode_raccordement"]:
            for matiere in Variables_score["periode_raccordement"][etudiant]:
                Obj.append(Variables_score["periode_raccordement"][etudiant][matiere])
    model.setObjective(gp.quicksum(Obj), GRB.MINIMIZE)

def ajout_variables_raccordement(model,Variables_score,Classes,planning_a_raccorder):
    """
    Ajoute les variables d'écarts de score en cas de raccordement, a appeler AVANT ajout_variable_score
    """
    Variables_score["ecarts_raccordement"]={}
    Variables_score["periode_raccordement"]={}
    for classe in Classes:
        nb_semaines=len(classe.semaines_colles)+len(planning_a_raccorder['semaines'])
        for etudiant in classe.etudiants:
            Variables_score["ecarts_raccordement"][etudiant]={}
            Variables_score["periode_raccordement"][etudiant]={}
            for matiere in classe.matieres:
                if set(matiere.options).intersection(set(etudiant.options)) and len(matiere.colleurs)>1:
                    Variables_score["periode_raccordement"][etudiant][matiere]=model.addVar(vtype=GRB.CONTINUOUS,name=f"x_score_raccordement_periode_{etudiant.nom}_{matiere.nom}") #Ajout de la variable pour le raccordement de la période de matière à l'étudiant
                    opt=list(set(matiere.options).intersection(set(etudiant.options)))[0] #On récupère l'option
                    somme_poids=sum([colleur.heures[matiere] for colleur in matiere.colleurs])
                    if int(somme_poids)==somme_poids: #S'il n'y a pas d'heures non entières
                        for colleur in matiere.colleurs:
                            Variables_score["ecarts_raccordement"][etudiant][colleur]={}
                            EC=ut.ecarts(colleur.heures[matiere],somme_poids)#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],colleur.heures[matiere],somme_poids,nb_semaines)
                            D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines'])) #On filtre pour ne garder que les éléments avec des chevauchements entre le raccord et le nouveau colloscope
                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts_raccordement"][etudiant][colleur][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts_raccordement"][etudiant][colleur][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_raccordement'+str(couple[0])+'semaines_depart_'+str(depart))
                    else:
                        for colleur in matiere.colleurs:
                            Variables_score["ecarts_raccordement"][etudiant][colleur]={}
                            Variables_score["ecarts_raccordement"][etudiant][colleur]["down"]={} #Cas où l'heure flexible saute pour l'étudiant à cause de son profil d'alternance de matières
                            EC=ut.ecarts(int(colleur.heures[matiere]),int(somme_poids))#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],int(colleur.heures[matiere]),int(somme_poids),nb_semaines)
                            D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines'])) #On filtre pour ne garder que les éléments avec des chevauchements entre le raccord et le nouveau colloscope
                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_raccordement_down_'+str(couple[0])+'semaines_depart_'+str(depart))
                            Variables_score["ecarts_raccordement"][etudiant][colleur]["up"]={} #Cas où l'heure flexible existe pour l'étudiant
                            if int(colleur.heures[matiere])==colleur.heures[matiere]:
                                h=colleur.heures[matiere]
                            else:
                                h=int(colleur.heures[matiere])+1
                            EC=ut.ecarts(h,int(somme_poids)+1)#On détermine les écarts à vérifier
                            D=ut.semaines_scores_ecarts(matiere.periodes[opt],h,int(somme_poids)+1,nb_semaines)
                            D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines'])) #On filtre pour ne garder que les éléments avec des chevauchements entre le raccord et le nouveau colloscope
                            for i,couple in enumerate(EC):
                                N=max([len(D[start][couple]) for start in D])
                                Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple]={}
                                for depart in range(N):
                                    Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple][depart]=model.addVar(vtype=GRB.CONTINUOUS,name='x_score_ecart_raccordement_up_'+str(couple[0])+'semaines_depart_'+str(depart))


# %% Equations groupes de colles



def equations_groupes(model,Variables,Classes,Equations):
    """
    Ajoute les équations au modèle permettant que les étudiants d'un même groupe soient affectés au mêmes horaires de colles pour les matières qui tiennent compte des groupes
    On prend en entrée la liste de toutes les classes (Classes)
    """
    for classe in Classes:
        if classe not in Equations:
            Equations[classe]={}
        if "equations_de_groupes" not in Equations[classe]:
            Equations[classe]["equations_de_groupes"]={}
        groupes_dict={} #On regroupe les étudiants avec le même groupe à l'aide d'un dictionnaire dont les clés sont les numéros de groupes
        for e in classe.etudiants:
            if e.groupe not in groupes_dict:
                groupes_dict[e.groupe]=[e]
            else:
                groupes_dict[e.groupe].append(e)
        for g in groupes_dict:
            if g not in Equations[classe]["equations_de_groupes"]:
                Equations[classe]["equations_de_groupes"][g]={}
            L=[]
            for etudiant in groupes_dict[g]:
                L.append(ut.find_paths_through_key(Variables,etudiant)) #On récupère les chemins valides du dictionnaire pour chaque étudiant du groupe
            Paths=ut.intersection_of_multiple_lists(*L) #On trouve les chemins communs
            for path in Paths:
                if len(path)==4: #Si le chemin correspond à semaine+matiere+colleur+horaire
                    (semaine,matiere,colleur,horaire)=path
                    if semaine not in Equations[classe]["equations_de_groupes"][g]:
                        Equations[classe]["equations_de_groupes"][g][semaine]={}
                    if matiere.groupes_fixes:
                        if matiere not in Equations[classe]["equations_de_groupes"][g][semaine]:
                            Equations[classe]["equations_de_groupes"][g][semaine][matiere]={}
                        if colleur not in Equations[classe]["equations_de_groupes"][g][semaine][matiere]:
                            Equations[classe]["equations_de_groupes"][g][semaine][matiere][colleur]={}
                        if horaire not in Equations[classe]["equations_de_groupes"][g][semaine][matiere][colleur]:
                            Equations[classe]["equations_de_groupes"][g][semaine][matiere][colleur][horaire]=[]
                        for etudiant1 in groupes_dict[g]:
                            for etudiant2 in groupes_dict[g]:
                                if etudiant1!=etudiant2:
                                    Equations[classe]["equations_de_groupes"][g][semaine][matiere][colleur][horaire].append(model.addConstr(Variables[semaine][etudiant1][matiere][colleur][horaire] == Variables[semaine][etudiant2][matiere][colleur][horaire], name='equation_groupe_de_colle_'+str(g)+'_'+classe.nom+'_groupe_'+str(g)))
                if len(path)==3: #Le chemin correspond à semaine+TP+horaire
                    (semaine,TP,horaire)=path
                    if semaine not in Equations[classe]["equations_de_groupes"][g]:
                        Equations[classe]["equations_de_groupes"][g][semaine]={}
                    if TP.groupes_fixes:
                        if TP not in Equations[classe]["equations_de_groupes"][g][semaine]:
                            Equations[classe]["equations_de_groupes"][g][semaine][TP]={}
                        if horaire not in Equations[classe]["equations_de_groupes"][g][semaine][TP]:
                            Equations[classe]["equations_de_groupes"][g][semaine][TP][horaire]=[]
                        for etudiant1 in groupes_dict[g]:
                            for etudiant2 in groupes_dict[g]:
                                if etudiant1!=etudiant2:
                                    Equations[classe]["equations_de_groupes"][g][semaine][TP][horaire].append(model.addConstr(Variables[semaine][etudiant1][TP][horaire] == Variables[semaine][etudiant2][TP][horaire], name='equation_groupe_de_colle_'+str(g)+'_'+classe.nom+'_groupe_'+str(g)))


# %% Equations alternance matieres et TP


def equations_somme_colles(model,Variables,Variables_aux,Classes,Equations):
    """
    Ajoute des équations permettant de fixer les variables auxiliaires égales à la somme des variables pour chaque étudiant/semaine/matiere ou TP
    """
    for classe in Classes:
        if classe not in Equations:
            Equations[classe]={}
        if "equations_somme_colles" not in Equations[classe]:
            Equations[classe]["equations_somme_colles"]={}
        for etudiant in classe.etudiants:
            Equations[classe]["equations_somme_colles"][etudiant]={}
            for semaine in classe.semaines_colles: #On gère les variables intermediaires donnant la somme des variables pour l'etudiant par semaine et par matiere/TP
                Equations[classe]["equations_somme_colles"][etudiant][semaine]={}
                for matiere in classe.matieres:
                    if set(matiere.options).intersection(set(etudiant.options)):
                        L=[]
                        for colleur in matiere.colleurs:
                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                        Equations[classe]["equations_somme_colles"][etudiant][semaine][matiere]=model.addConstr(gp.quicksum(L) == Variables_aux[classe][etudiant][semaine][matiere],name='equation_somme_colles_'+etudiant.nom+"_"+'semaine_'+str(semaine)+'_'+matiere.nom)
                for TP in classe.TP:
                    if set(TP.options).intersection(set(etudiant.options)): #On vérifie si une option correspond
                        L=[Variables[semaine][etudiant][TP][horaire] for horaire in Variables[semaine][etudiant][TP]]
                        Equations[classe]["equations_somme_colles"][etudiant][semaine][TP]=model.addConstr(gp.quicksum(L) == Variables_aux[classe][etudiant][semaine][TP],name='equation_somme_colles_'+etudiant.nom+"_"+'semaine_'+str(semaine)+'_'+TP.nom)


def equations_debut_periodes(model,Variables,Variables_aux,Classes,Equations):
    """
    Ajoute les équations pour les variables auxiliaires de début de période, pour les matieres/TP à alternance fixe et les équations pour les débuts de période pour chaque étudiant
    """
    for classe in Classes:
        if classe not in Equations:
            Equations[classe]={}
        if "debut_periodes" not in Equations[classe]:
            Equations[classe]["debut_periodes"]={}
        for key in Variables_aux[classe]["fixe"]:
            if key not in Equations[classe]["debut_periodes"]:
                Equations[classe]["debut_periodes"][key]={}
            for MT in Variables_aux[classe]["fixe"][key]: #La somme des variables de debut de periode doit etre egale a 1 (la seule variable egale a 1 correspond au debut de periode pour cette matiere/TP)
                Equations[classe]["debut_periodes"][key][MT]=model.addConstr(gp.quicksum(Variables_aux[classe]["fixe"][key][MT])==1,name="equation_debut_periode_"+classe.nom+"_"+MT.nom)
        for etudiant in classe.etudiants: #On ajoute les equations de debut_periode pour chaque etudiant
            Equations[classe]["debut_periodes"][etudiant]={}
            Equations[classe]["debut_periodes"][etudiant]['fixe']=model.addConstr(gp.quicksum(Variables_aux[classe][etudiant]["debut_periode"]['fixe'])==1 ,name= "equation_debut_periode_fixe_"+classe.nom+"_"+etudiant.nom) #On ajoute d'abord l'équation de début de période pour le groupe de matieres a alternance fixe
            Equations[classe]["debut_periodes"][etudiant]['flexible']={}
            for matiere in Variables_aux[classe][etudiant]["debut_periode"]['flexible']: #Pour chaque matiere flexible
                Equations[classe]["debut_periodes"][etudiant]['flexible'][matiere]=model.addConstr(gp.quicksum(Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere])==1 ,name= "equation_debut_periode_"+classe.nom+"_"+matiere.nom+'_'+etudiant.nom) #On ajoute l'équation de début de période pour cette matiere (ou TP)


def equations_alternance_matieres_TP(model,Variables,Variables_aux,Classes,Equations,planning_a_raccorder=None):
    """
    Ajoute les équations au modèle permettant que l'alternance des matières/TP pour chaque étudiant soit bien respectée selon les périodes indiquées dans les matières/TP
    """
    for classe in Classes:
        if classe not in Equations:
            Equations[classe]={}
        if "alternance_matieres" not in Equations[classe]:
            Equations[classe]["alternance_matieres"]={}
        for etudiant in classe.etudiants:
            Equations[classe]["alternance_matieres"][etudiant]={}
            for s,semaine in enumerate(classe.semaines_colles):
                for MT in Variables_aux[classe][etudiant][semaine]:
                    Equations[classe]["alternance_matieres"][etudiant][MT]=[]
                    option=etudiant.trouver_option(MT)
                    if s<MT.decalage_semaines: #Si on est sur une semaine ou les colles de la matiere n'ont pas demarré
                        Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(Variables_aux[classe][etudiant][semaine][MT]== 0,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)))
                    elif s>=len(MT.periodes[option])+MT.decalage_semaines:#Si on est sur une semaine dont le numero depasse la longueur de la periode (augmentée du décalage du début des colles)
                        nb_colles=0
                        if planning_a_raccorder and MT in planning_a_raccorder['matieres_etudiant'][etudiant]:
                            nb_colles=sum([planning_a_raccorder['matieres_etudiant'][etudiant][MT][s] for s in planning_a_raccorder['semaines']])
                        if MT in classe.matieres and (s//len(MT.periodes[option]))*sum([int(d) for d in MT.periodes[option]])+sum([int(MT.periodes[option][i]) for i in range(s%len(MT.periodes[option]))])+nb_colles>=MT.nbCollesMax: #Si on a deja atteint le nombre de colles max dans l'annee
                            Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(Variables_aux[classe][etudiant][semaine][MT]== 0,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)))
                        else:
                            semaine_p1=classe.semaines_colles[s%len(MT.periodes[option])]
                            Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(Variables_aux[classe][etudiant][semaine][MT]== Variables_aux[classe][etudiant][semaine_p1][MT],name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine))) #On copie la valeur de la semaine correspondante sur la p1
                    else: #semaine de la p1 pour la matiere correspondante
                        if MT.alternance_fixe: #Si c'est une matiere/TP a alternance_fixe
                            key=tuple(etudiant.options)
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']): #On ecrit une equation pour chaque debut de periode possible pour l'etudiant et chaque debut possible de matiere/TP
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][MT]):
                                    if MT.periodes[option][(i+j+s)%len(MT.periodes[option])]=='1':
                                        Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(1-dpe+1-dpm+Variables_aux[classe][etudiant][semaine][MT]>=1,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)+'_dpe'+str(i)+'_dpm'+str(j)))
                                    else:
                                        Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(1-dpe+1-dpm+1-Variables_aux[classe][etudiant][semaine][MT]>=1,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)+'_dpe'+str(i)+'_dpm'+str(j)))
                        else: #matiere flexible
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['flexible'][MT]): #On ecrit une equation pour chaque debut possible de periode pour l'etudiant dans cette matiere
                                    if MT.periodes[option][(i+s)%len(MT.periodes[option])]=='1':
                                        Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(1-dpe+Variables_aux[classe][etudiant][semaine][MT]>=1,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)+'_dpe'+str(i)))
                                    else:
                                        Equations[classe]["alternance_matieres"][etudiant][MT].append(model.addConstr(1-dpe+1-Variables_aux[classe][etudiant][semaine][MT]>=1,name='equation_alternance_'+classe.nom+'_'+etudiant.nom+'_'+MT.nom+'_semaine'+str(semaine)+'_dpe'+str(i)))





def equations_matieres_groupees(model,Variables_aux,Classes,Equations):
    """
    Ajoute les équations au modèle permettant que les matières/TP liées respectent l'alternance entre elles qui a été fixée
    """
    Equations["matieres_groupees"]={}
    for classe in Classes:
        if classe not in Equations["matieres_groupees"]:
            Equations["matieres_groupees"][classe]=[]
        for thing in classe.matieres_groupees:
            (TupMT,option)=thing
            MT1=TupMT[0]
            for i,MT2 in enumerate(TupMT):
                if i!=0:
                    Find_Keys=[key for key in Variables_aux[classe]['fixe'] if option in key]
                    for key in Find_Keys:
                        for j,dpmt1 in enumerate(Variables_aux[classe]['fixe'][key][MT1]):
                            l=len(MT2.periodes[option]) #on récupère la période correspondante
                            decalage=classe.matieres_groupees[thing][i]-classe.matieres_groupees[thing][0] #On recupere le decalage de periode entre les deux matieres
                            dpmt2=Variables_aux[classe]['fixe'][key][MT2][(j+decalage)%l] #On recupere la variable debut_periode correspondante
                            Equations["matieres_groupees"][classe].append(model.addConstr(1-dpmt1+dpmt2>=1,name='equation_groupement_option_'+option+'_'+MT1.nom+'_'+MT2.nom+'_dp'+str(j)))#On ajoute l'égalité entre les débuts de période en tenant compte du décalage



# %% Equations overlaps

def equation_overlaps(model,Variables,Classes,Equations):
    """
    Ajoute les équations au modèle permettant que les élèves n'aient pas plusieurs colles en même temps
    """
    for classe in Classes:
        #print(classe.nom)
        CM=classe.groupes_horaires_overlap()
        if classe not in Equations:
            Equations[classe]={}
        Equations[classe]["overlaps"]={}
        for semaine in classe.semaines_colles:
            #print(semaine)
            Equations[classe]["overlaps"][semaine]={}
            for etudiant in classe.etudiants:
                Paths=ut.find_paths_through_key(Variables[semaine],etudiant) #On récupère tous les chemins menant à une variable
                Horaires_etudiant_semaine=[path[-1] for path in Paths]
                Equations[classe]["overlaps"][semaine][etudiant]=[]
                Groupes_Paths=[[path for path in Paths if path[-1] in G] for G in CM]
                for k,groupe in enumerate(Groupes_Paths):
                    Vars=[]
                    for path in groupe:
                        if len(path)==3:
                            (matiere,colleur,h)=path
                            if matiere in Variables[semaine][etudiant]:
                                if colleur in Variables[semaine][etudiant][matiere]:
                                    if h in Variables[semaine][etudiant][matiere][colleur]:
                                        Vars.append(Variables[semaine][etudiant][matiere][colleur][h])
                        if len(path)==2:
                            (TP,h)=path
                            if TP in Variables[semaine][etudiant]:
                                if h in Variables[semaine][etudiant][TP]:
                                    Vars.append(Variables[semaine][etudiant][TP][h])
                    Equations[classe]["overlaps"][semaine][etudiant].append(model.addConstr(gp.quicksum(Vars)<=1,name='equation_overlap_semaine'+str(semaine)+'_etudiant_'+etudiant.nom+'_clique'+str(k))) #La somme des variables doit forcément être inférieure ou égale à 1 pour éviter des overlaps


# %% Equations horaires non entiers colleurs


def equations_occupation_creneaux(model,Variables,Variables_aux,Equations,Colleurs):
    """
    Crée les équations permettant de fixer les valeurs des variables logiques d'occupation de créneau
    """
    Equations["occupation_creneaux"]={}
    for colleur in Colleurs:
        Equations["occupation_creneaux"][colleur]={}
        for matiere in colleur.matieres:
            Equations["occupation_creneaux"][colleur][matiere]={}
            for i,horaire in enumerate(colleur.horaires):
                if matiere in horaire.matieres:
                    Equations["occupation_creneaux"][colleur][matiere][horaire]={}
                    for semaine in horaire.semaines:
                        if semaine in Variables and semaine in matiere.classe.semaines_colles:
                            L=[]
                            Equations["occupation_creneaux"][colleur][matiere][horaire][semaine]=[]
                            Paths=ut.find_paths_through_key(Variables[semaine],horaire) #On récupère les chemins menant à horaire à partir de semaine dans le dictionnaire Variables. A priori, on doit récupérer autant de chemin que d'étudiants possiblement concernés par cet horaire, car horaire n'apparaît que dans un seul colleur (mais peut être associé à plusieurs matières)
                            for path in Paths:
                                etudiant=path[0]
                                if matiere==path[1]:
                                    L.append(Variables[semaine][etudiant][matiere][colleur][horaire])
                            Equations["occupation_creneaux"][colleur][matiere][horaire][semaine].append(model.addConstr(gp.quicksum(L)>=Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine],name="equation1_occupation_creneau_"+colleur.nom+"_horaire_"+str(i)+"_semaine_"+str(semaine))) #On ajoute la contrainte : si la variable logique associée vaut 1 alors il y a au moins une variable associée à ce créneau qi vaut 1
                            Equations["occupation_creneaux"][colleur][matiere][horaire][semaine].append(model.addConstr(gp.quicksum(L)<=len(L)*Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine],name="equation2_occupation_creneau_"+colleur.nom+"_horaire_"+str(i)+"_semaine_"+str(semaine)))  #On ajoute la contrainte : si la variable logique associée vaut 0 alors la somme des variables associées vaut 0

def equations_horaires_non_entiers(model,Variables,Variables_aux,Equations,Classes):
    """
    Permet de s'assurer que les horaires non entiers soient "dégagés" avant les horaires entiers
    """
    Equations["horaires_partiels"]={}
    for classe in Classes:
        for matiere in classe.matieres:
            Equations["horaires_partiels"][matiere]={}
            for semaine in classe.semaines_colles:
                Equations["horaires_partiels"][matiere][semaine]=[]
                L_full=[] # On va récupérer la liste des variables d'occupation associées aux horaires fixes (poids=1) pour la semaine et la matière donnée
                L_partial=[] #La liste des variables d'occupation pour les horaires de poids<1 pour la semaine et la matière donnée
                for colleur in matiere.colleurs:
                    for horaire in colleur.horaires:
                        if matiere in horaire.matieres and semaine in horaire.semaines:
                            if horaire.flexible:
                                L_partial.append(Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine])
                            else:
                                Temp=[]
                                for mat in horaire.matieres:
                                    if semaine in mat.classe.semaines_colles:
                                        Temp.append(Variables_aux["occupation_creneaux"][colleur][mat][horaire][semaine])
                                L_full.append(Temp)
                for i,var1list in enumerate(L_full):
                    for j,var2 in enumerate(L_partial):
                        Equations["horaires_partiels"][matiere][semaine].append(model.addConstr(var2<=gp.quicksum(var1list),name="equation_horaire_partiels_"+matiere.nom+'_'+classe.nom+"_semaine_"+str(semaine)+"n_"+str(i)+"_"+str(j))) #Pour chaque horaire partiel, l'occupation ne doit pas être égale à 1 si l'un des horaires fixes a une occupation égale à 0





# %% Equations nombre de colles max


def equations_nombre_max_colles_etudiant(model,Variables,Equations):
    """
    Permet de respecter le nombre maximum de colles par semaine pour chaque étudiant
    """
    Equations["nombre_max_colles"]={}
    for semaine in Variables:
        Equations["nombre_max_colles"][semaine]={}
        for etudiant in Variables[semaine]:
            classe=etudiant.classe
            nbmax=classe.nbCollesMax
            L=[]
            for matiere in classe.matieres:
                if matiere in Variables[semaine][etudiant]:
                    for colleur in Variables[semaine][etudiant][matiere]:
                        for horaire in Variables[semaine][etudiant][matiere][colleur]:
                            L.append(Variables[semaine][etudiant][matiere][colleur][horaire])
            Equations["nombre_max_colles"][semaine][etudiant]=model.addConstr(gp.quicksum(L)<=nbmax,name="equation_nb_max_colles_semaine_"+str(semaine)+'_'+etudiant.nom)


# %% Equations colleurs multi-classes

def equations_colleurs_multi_classes(model,Variables_aux,Equations):
    """
    Permet que les colleurs qui aient des créneaux affectés à plusieurs classes sur des matières où les colles ne sont pas par groupe de n'avoir que des élèves de la même classe
    BUG-> Empeche de trouver une solution, fonction a FIXER
    """
    Equations["colleurs_multi_classes"]={}
    for colleur in Variables_aux["occupation_creneaux"]:
        Equations["colleurs_multi_classes"][colleur]={}
        for i,horaire in enumerate(colleur.horaires):
            Equations["colleurs_multi_classes"][colleur][horaire]={}
            if len(horaire.matieres)>1:
                L=[]
                for semaine in horaire.semaines:
                    for matiere in horaire.matieres:
                        if semaine in Variables_aux["occupation_creneaux"][colleur][matiere][horaire]:
                            L.append(Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine])
                    Equations["colleurs_multi_classes"][colleur][horaire][semaine]=model.addConstr(gp.quicksum(L)<=1,name="equation_colleur_multi_classe_"+colleur.nom+"_horaire_"+str(i)+"semaine_"+str(semaine))

def equations_heures(model,Variables_aux,Equations):
    """
    Permet que les colleurs respectent bien le nombre d'heures prevues par classes.
    """
    Equations["heures_multi_classes"]={}
    for colleur in Variables_aux["occupation_creneaux"]:
        Equations["heures_multi_classes"][colleur]={}
        for matiere in Variables_aux["occupation_creneaux"][colleur]:
            if int(colleur.heures[matiere])==colleur.heures[matiere]:
                nb_heures_max=int(colleur.heures[matiere])
            else:
                nb_heures_max=int(colleur.heures[matiere])+1
            #nb_heures_min=int(colleur.heures[matiere])
            Equations["heures_multi_classes"][colleur][matiere]={}
            for semaine in matiere.classe.semaines_colles:
                L=[]
                for horaire in colleur.horaires:
                    if matiere in horaire.matieres and semaine in horaire.semaines:
                        L.append(Variables_aux["occupation_creneaux"][colleur][matiere][horaire][semaine])
                Equations["heures_multi_classes"][colleur][matiere][semaine]=[]
                Equations["heures_multi_classes"][colleur][matiere][semaine].append(model.addConstr(gp.quicksum(L)<=nb_heures_max,name="equation_heures_max_"+colleur.nom+"_"+matiere.classe.nom+"_"+matiere.nom+"_semaine"+str(semaine)))
                #Equations["heures_multi_classes"][colleur][matiere][semaine].append(model.addConstr(gp.quicksum(L)>=nb_heures_min,name="equation_heures_min_"+colleur.nom+"_"+matiere.classe.nom+"_"+matiere.nom+"_semaine"+str(semaine)))





# %% Equations places en TP et colles

def equations_places_TP_colles(model,Variables,Classes,Equations):
    """
    Permet de s'assurer que le nombre d'élèves sur un TP ou une colle n'excède pas le nombre max fixé
    """
    Equations["places_colles"]={}
    Equations["places_TP"]={}
    for classe in Classes:
        for semaine in classe.semaines_colles:
            Equations["places_colles"][semaine]={}
            Equations["places_TP"][semaine]={}
            for matiere in classe.matieres:
                for colleur in matiere.colleurs:
                    for i,horaire in enumerate(colleur.horaires):
                        Paths=ut.find_paths_through_key(Variables[semaine],horaire)
                        L=[]
                        M=horaire.places
                        for path in Paths:
                            etudiant=path[0]
                            matiere=path[1]
                            L.append(Variables[semaine][etudiant][matiere][colleur][horaire])
                        Equations["places_colles"][semaine][horaire]=model.addConstr(gp.quicksum(L)<=M,name="equation_nb_places_"+classe.nom+'_'+matiere.nom+'_'+colleur.nom+'horaire_'+str(i))
            for TP in classe.TP:
                for i,horaire in enumerate(TP.horaires):
                    Paths=ut.find_paths_through_key(Variables[semaine],horaire)
                    L=[]
                    M=horaire.places
                    for path in Paths:
                        etudiant=path[0]
                        L.append(Variables[semaine][etudiant][TP][horaire])
                    Equations["places_TP"][semaine][TP]=model.addConstr(gp.quicksum(L)<=M,name="equation_nb_places_"+classe.nom+'_'+TP.nom+'_'+'horaire_'+str(i))

# %% Equations de score

def equations_score(model,Variables,Variables_score,Variables_aux,Equations):
    """
    Permet d'ajouter les équations sur les variables d'écart qui définissent l'objectif d'optimisation
    """
    Equations["score"]={}
    for etudiant in Variables_score['ecarts']:
        Equations["score"][etudiant]={}
        for colleur in Variables_score["ecarts"][etudiant]:
            Equations["score"][etudiant][colleur]={}
            if "up" not in Variables_score["ecarts"][etudiant][colleur]: #Cas plus simple ou la somme des poids est entiere
                matiere=list(set(colleur.matieres).intersection(set(etudiant.classe.matieres)))[0]
                classe=etudiant.classe
                opt=list(set(matiere.options).intersection(set(etudiant.options)))[0]
                somme_poids=sum([cl.heures[matiere] for cl in matiere.colleurs])
                nb_semaines=len(etudiant.classe.semaines_colles)
                key=tuple(etudiant.options)
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],colleur.heures[matiere],somme_poids,nb_semaines)
                EC=ut.ecarts(colleur.heures[matiere],somme_poids)
                M=nb_semaines**3 #Sert a désactiver les contraintes quand les variables logiques pertinentes ne sont pas égales à 1
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur][couple]:
                            Equations["score"][etudiant][colleur][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur][couple][start]
                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, i+j%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                                    L=[]
                                    if start<len(D[(i+j)%len(matiere.periodes[opt])][couple]):
                                        for s in D[(i+j)%len(matiere.periodes[opt])][couple][start]:
                                            semaine=classe.semaines_colles[s]
                                            if colleur in Variables[semaine][etudiant][matiere]:
                                                L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L) -(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur][couple]:
                            Equations["score"][etudiant][colleur][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur][couple][start]
                            Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                                L=[]
                                if start<len(D[i][couple]):
                                    for s in D[i][couple][start]:
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M ,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L) -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                    Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                    Equations["score"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
            else: #cas où la somme des poids n'est pas entiere, on calcule les ecarts "up" et "down" (étudiant concerné ou pas par le créneau flexible et l'écart global est fixé au minimum des deux
                Equations["score"][etudiant][colleur]["down"]={}
                matiere=list(set(colleur.matieres).intersection(set(etudiant.classe.matieres)))[0]
                classe=etudiant.classe
                opt=list(set(matiere.options).intersection(set(etudiant.options)))[0]
                somme_poids=int(sum([cl.heures[matiere] for cl in matiere.colleurs])) #On arrondit à l'inférieur (down)
                nb_semaines=len(etudiant.classe.semaines_colles)
                key=tuple(etudiant.options)
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],int(colleur.heures[matiere]),somme_poids,nb_semaines)
                EC=ut.ecarts(int(colleur.heures[matiere]),somme_poids)
                M=nb_semaines**3 #Sert a désactiver les contraintes quand les variables logiques pertinentes ne sont pas égales à 1
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur]["down"][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur]["down"][couple]:
                            Equations["score"][etudiant][colleur]["down"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur]["down"][couple][start]
                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, i+j%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                                    L=[]
                                    if start<len(D[(i+j)%len(matiere.periodes[opt])][couple]):
                                        for s in D[(i+j)%len(matiere.periodes[opt])][couple][start]:
                                            semaine=classe.semaines_colles[s]
                                            if colleur in Variables[semaine][etudiant][matiere]:
                                                L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]

                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L) -(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur]["down"][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur]["down"][couple]:
                            Equations["score"][etudiant][colleur]["down"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur]["down"][couple][start]
                            Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                                L=[]
                                if start<len(D[i][couple]):
                                    for s in D[i][couple][start]:
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M ,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L) -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                    else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                        Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        Equations["score"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))

                Equations["score"][etudiant][colleur]["up"]={}
                somme_poids=int(sum([cl.heures[matiere] for cl in matiere.colleurs]))+1 #On arrondit au supérieur (up)
                h=int(colleur.heures[matiere])
                if h!=colleur.heures[matiere]:
                    h+=1
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],h,somme_poids,nb_semaines)
                EC=ut.ecarts(h,somme_poids)
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur]["up"][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur]["up"][couple]:
                            Equations["score"][etudiant][colleur]["up"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur]["up"][couple][start]
                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, i+j%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                                    L=[]
                                    if start<len(D[(i+j)%len(matiere.periodes[opt])][couple]):
                                        for s in D[(i+j)%len(matiere.periodes[opt])][couple][start]:
                                            semaine=classe.semaines_colles[s]
                                            if colleur in Variables[semaine][etudiant][matiere]:
                                                L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]

                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L) -(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(2-dpe-dpm)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score"][etudiant][colleur]["up"][couple]={}
                        for start in Variables_score["ecarts"][etudiant][colleur]["up"][couple]:
                            Equations["score"][etudiant][colleur]["up"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts"][etudiant][colleur]["up"][couple][start]
                            Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                                L=[]
                                if start<len(D[i][couple]):
                                    for s in D[i][couple][start]:
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M ,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L) -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                    else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                        Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)-couple[1]-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))
                                        Equations["score"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-(1-dpe)*M,name="equation_score_"+etudiant.nom+'_'+colleur.nom))

def equations_score_raccordement_ecarts(model,Variables,Variables_score,Variables_aux,Equations,planning_a_raccorder):
    """
    Permet d'ajouter les équations sur les variables d'écart qui définissent l'objectif d'optimisation
    """
    Equations["score_raccordement"]={}
    for etudiant in Variables_score['ecarts_raccordement']:
        Equations["score_raccordement"][etudiant]={}
        for colleur in Variables_score["ecarts_raccordement"][etudiant]:
            Equations["score_raccordement"][etudiant][colleur]={}
            if "up" not in Variables_score["ecarts_raccordement"][etudiant][colleur]: #Cas plus simple ou la somme des poids est entiere
                matiere=list(set(colleur.matieres).intersection(set(etudiant.classe.matieres)))[0]
                classe=etudiant.classe
                opt=list(set(matiere.options).intersection(set(etudiant.options)))[0]
                somme_poids=sum([cl.heures[matiere] for cl in matiere.colleurs])
                nb_semaines=len(etudiant.classe.semaines_colles)+len(planning_a_raccorder['semaines'])
                key=tuple(etudiant.options)
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],colleur.heures[matiere],somme_poids,nb_semaines)
                D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines']))
                EC=ut.ecarts(colleur.heures[matiere],somme_poids)
                M=nb_semaines**3 #Sert a désactiver les contraintes quand les variables logiques pertinentes ne sont pas égales à 1
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur][couple]:
                            Equations["score_raccordement"][etudiant][colleur][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur][couple][start]
                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, (i+j%len(periode)+len(planning_a_raccorder['semaines']))%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant en tenant compte du raccord
                                    L=[] #Liste des variables à considérer
                                    debut_periode=((i+j)%len(matiere.periodes[opt])+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                    if start<len(D[debut_periode][couple]):
                                        Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                        nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                        Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                        for s in D[debut_periode][couple][start]:
                                            if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                                semaine=classe.semaines_colles[s]
                                                if colleur in Variables[semaine][etudiant][matiere]:
                                                    L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L)-Oc -(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur][couple]:
                            Equations["score_raccordement"][etudiant][colleur][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur][couple][start]
                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:#Le début de période est (i+len(planning_a_raccorder['semaines']))%len(periode)
                                L=[]
                                debut_periode=(i+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                if start<len(D[debut_periode][couple]):
                                    Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                    nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                    Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                    for s in D[debut_periode][couple][start]:
                                        if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                            semaine=classe.semaines_colles[s]
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M ,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L)-Oc -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
            else: #cas où la somme des poids n'est pas entiere, on calcule les ecarts "up" et "down" (étudiant concerné ou pas par le créneau flexible et l'écart global est fixé au minimum des deux
                Equations["score_raccordement"][etudiant][colleur]["down"]={}
                matiere=list(set(colleur.matieres).intersection(set(etudiant.classe.matieres)))[0]
                classe=etudiant.classe
                opt=list(set(matiere.options).intersection(set(etudiant.options)))[0]
                somme_poids=int(sum([cl.heures[matiere] for cl in matiere.colleurs])) #On arrondit à l'inférieur (down)
                nb_semaines=len(etudiant.classe.semaines_colles)
                key=tuple(etudiant.options)
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],int(colleur.heures[matiere]),somme_poids,nb_semaines)
                D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines']))
                EC=ut.ecarts(int(colleur.heures[matiere]),somme_poids)
                M=nb_semaines**3 #Sert a désactiver les contraintes quand les variables logiques pertinentes ne sont pas égales à 1
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur]["down"][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple]:
                            Equations["score_raccordement"][etudiant][colleur]["down"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple][start]
                            Equations["score_raccordement"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, i+j%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                                    L=[]
                                    debut_periode=((i+j)%len(matiere.periodes[opt])+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                    if start<len(D[debut_periode][couple]):
                                        Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                        nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                        Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                        for s in D[debut_periode][couple][start]:
                                            if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                                semaine=classe.semaines_colles[s]
                                                if colleur in Variables[semaine][etudiant][matiere]:
                                                    L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L)-Oc -(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur]["down"][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple]:
                            Equations["score_raccordement"][etudiant][colleur]["down"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple][start]
                            Equations["score_raccordement"][etudiant][colleur]["down"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                                L=[]
                                debut_periode=(i+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                if start<len(D[debut_periode][couple]):
                                    Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                    nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                    Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                    for s in D[debut_periode][couple][start]:
                                        if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                            semaine=classe.semaines_colles[s]
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M ,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L)-Oc -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))

                Equations["score_raccordement"][etudiant][colleur]["up"]={}
                somme_poids=int(sum([cl.heures[matiere] for cl in matiere.colleurs]))+1 #On arrondit au supérieur (up)
                h=int(colleur.heures[matiere])
                if h!=colleur.heures[matiere]:
                    h+=1
                D=ut.semaines_scores_ecarts(matiere.periodes[opt],h,somme_poids,nb_semaines)
                D=ut.filtre_semaine_scores_ecarts(D,len(planning_a_raccorder['semaines']))
                EC=ut.ecarts(h,somme_poids)
                if matiere.alternance_fixe: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer !
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur]["up"][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple]:
                            Equations["score_raccordement"][etudiant][colleur]["up"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple][start]
                            Equations["score_raccordement"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                                for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, i+j%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                                    L=[]
                                    debut_periode=((i+j)%len(matiere.periodes[opt])+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                    if start<len(D[debut_periode][couple]):
                                        Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                        nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                        Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                        for s in D[debut_periode][couple][start]:
                                            if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                                semaine=classe.semaines_colles[s]
                                                if colleur in Variables[semaine][etudiant][matiere]:
                                                    L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                        if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=couple[1]-gp.quicksum(L)-Oc -(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                            Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(2-dpe-dpm)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                else: #matiere a part, il y a une seule variable de debut de periode pour l'etudiant
                    for k,couple in enumerate(EC):
                        Equations["score_raccordement"][etudiant][colleur]["up"][couple]={}
                        for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple]:
                            Equations["score_raccordement"][etudiant][colleur]["up"][couple][start]=[]
                            Var_ecart=Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple][start]
                            Equations["score_raccordement"][etudiant][colleur]["up"][couple][start].append(model.addConstr(Var_ecart>=0,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom)) #Pour ne pas avoir de solutions non bornées
                            for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                                L=[]
                                debut_periode=(i+len(planning_a_raccorder['semaines']))%len(matiere.periodes[opt])
                                if start<len(D[debut_periode][couple]):
                                    Semaines_matieres=[s for s in planning_a_raccorder['semaines'] if planning_a_raccorder['matieres_etudiant'][etudiant][matiere][s]==1] #On récupère la liste des semaines où l'étudiant a eu une colle de cette matière dans le planning a raccorder
                                    nbsr= len([i for i in D[debut_periode][couple][start] if i<len(planning_a_raccorder['semaines'])]) # nombre de semaines à raccorder
                                    Oc=sum([planning_a_raccorder['colleurs_etudiant'][etudiant][colleur][s] for s in Semaines_matieres[-nbsr:]  ]) #Nombre d'occurences du colleur dans les semaines précédant le raccord
                                    for s in D[debut_periode][couple][start]:
                                        if s>=len(planning_a_raccorder['semaines']): #semaine sur le nouveau colloscope
                                            semaine=classe.semaines_colles[s]
                                        semaine=classe.semaines_colles[s]
                                        if colleur in Variables[semaine][etudiant][matiere]:
                                            L+=[Variables[semaine][etudiant][matiere][colleur][horaire] for horaire in Variables[semaine][etudiant][matiere][colleur]]
                                    model.addConstr(Var_ecarts>=0) #Pour ne pas avoir de solutions non bornées
                                    if k==len(EC)-1: #Dernier élément de la liste écarts, le nombre de colles doit être égal
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M ,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                        model.addContr(Var_ecarts>=couple[1]-gp.quicksum(L)-Oc -(1-dpe)*M)
                                    elif k==0: #Premier élément de la liste écarts, le nombre de colle doit être inférieur ou égal à 1
                                        Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                else: #Le nombre de colles doit être entre la valeur correspondante de l'indice et celle d'avant
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=gp.quicksum(L)+Oc-couple[1]-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))
                                    Equations["score_raccordement"][etudiant][colleur][couple][start].append(model.addConstr(Var_ecart>=EC[k-1][1]-gp.quicksum(L)-Oc-(1-dpe)*M,name="equation_score_raccordement_"+etudiant.nom+'_'+colleur.nom))


def equations_raccordement_periodes(model,Variables_aux,Variables_score,Equations,planning_a_raccorder):
    """
    Ajoute les equations permettant de calculer les penalites en cas d'erreur de raccordement
    """
    Equations["raccordement_periodes"]={}
    for etudiant in Variables_score["periode_raccordement"]:
        classe=etudiant.classe
        key=tuple(etudiant.options)
        Equations["raccordement_periodes"][etudiant]={}
        for matiere in Variables_score["periode_raccordement"][etudiant]:
            V=Variables_score["periode_raccordement"][etudiant][matiere]
            Equations["raccordement_periodes"][etudiant][matiere]=[]
            Equations["raccordement_periodes"][etudiant][matiere].append(model.addConstr(V>=0,name=f"equation_raccordement_periode_{etudiant.nom}_{matiere.nom}"))
            opt=list(set(matiere.options).intersection(set(etudiant.options)))[0] #On récupère l'option
            p=matiere.periodes[opt]
            l=len(p)

            if matiere.alternance_fixe and l>1: #Matiere presente dans le groupement des matieres, il y a deux variables de debut de periode a considerer. On ne considère pas les matières avec période 1
                for i,dpe in enumerate(Variables_aux[classe][etudiant]["debut_periode"]['fixe']):#début de période étudiant pour le groupement de matières fixes
                    for j,dpm in enumerate(Variables_aux[classe]["fixe"][key][matiere]): #début de période matière dans le groupement, (i+j)%len(periode) correspondra donc au début de la période dans la matière pour l'étudiant
                        dp=p[(i+j)%l:]+p[:(i+j%l)] #Periode decalee en tenant compte du début de période choisi
                        doublep=dp+dp #on recopie la periode
                        testp=dp #On recupere la période à raccorder
                        k=1
                        a=1
                        S=planning_a_raccorder['semaines']
                        while True: #On va allonger la periode "vers l'arriere" pour verifier si le raccordement est bien fait
                            testp= str(planning_a_raccorder['matieres_etudiant'][etudiant][matiere][S[-k]]) +testp
                            if testp not in doublep:
                                break
                            elif k==l:
                                a=0
                                break
                            k+=1
                        bigM=l*100
                        Equations["raccordement_periodes"][etudiant][matiere].append(model.addConstr(V>=100*(l-k+a)-bigM*(2-dpe-dpm),name=f"equation_raccordement_periode_{etudiant.nom}_{matiere.nom}"))
            elif l>1: #Un seul debut de periode a considerer
                for i,dpe in Variables_aux[classe][etudiant]["debut_periode"]['flexible'][matiere]:
                    p=p[i%l:]+p[:i%l] #Periode decalee en tenant compte du début de période choisi
                    doublep=p+p #on recopie la periode
                    testp=p #On recupere la période à raccorder
                    k=1
                    a=1
                    S=planning_a_raccorder['semaines']
                    while True: #On va allonger la periode "vers l'arriere" pour verifier si le raccordement est bien fait
                        testp= str(planning_a_raccorder['matieres_etudiant'][etudiant][matiere][S[-k]]) +testp
                        if testp not in doublep:
                            break
                        elif k==l:
                            a=0
                            break
                        k+=1
                    bigM=100*l
                    Equations["raccordement_periodes"][etudiant][matiere].append(model.addConstr(V>=100*(l-k+a)-bigM*(1-dpe),name=f"equation_raccordement_periode_{etudiant.nom}_{matiere.nom}"))


def equations_sommes_scores(model,Variables_score,Equations):
    """
    Pour fixer les variables de sommes d'écarts qui serviront d'objectif
    """
    Equations["sommes_scores"]={}
    for etudiant in Variables_score['ecarts']:
        Equations["sommes_scores"][etudiant]={}
        for colleur in Variables_score['ecarts'][etudiant]:
            if "up" not in Variables_score['ecarts'][etudiant][colleur]:
                L=[]
                for couple in Variables_score['ecarts'][etudiant][colleur]:
                    for start in Variables_score['ecarts'][etudiant][colleur][couple]:
                        L.append(Variables_score['ecarts'][etudiant][colleur][couple][start])
                if "ecarts_raccordement" in Variables_score:
                    if etudiant in Variables_score["ecarts_raccordement"]:
                        if colleur in Variables_score["ecarts_raccordement"][etudiant]:
                            for couple in Variables_score["ecarts_raccordement"][etudiant][colleur]:
                                for start in Variables_score["ecarts_raccordement"][etudiant][colleur][couple]:
                                    L.append(Variables_score["ecarts_raccordement"][etudiant][colleur][couple][start])
                Equations["sommes_scores"][etudiant][colleur]=model.addConstr(gp.quicksum(L)==Variables_score['somme'][etudiant][colleur]['tot'],name='equation_somme_scores_'+etudiant.nom+'_'+colleur.nom)
            else:
                Equations["sommes_scores"][etudiant][colleur]={}
                Equations["sommes_scores"][etudiant][colleur]['up']=[]
                Equations["sommes_scores"][etudiant][colleur]['down']=[]
                M=len(etudiant.classe.semaines_colles)**3
                L=[]
                Vardown=Variables_score['somme'][etudiant][colleur]['down']
                VarUp=Variables_score['somme'][etudiant][colleur]['up']
                VarTot=Variables_score['somme'][etudiant][colleur]['tot']
                a=Variables_score['somme'][etudiant][colleur]['choix']
                for couple in Variables_score['ecarts'][etudiant][colleur]["up"]:
                    for start in Variables_score['ecarts'][etudiant][colleur]["up"][couple]:
                        L.append(Variables_score['ecarts'][etudiant][colleur]["up"][couple][start])
                if "ecarts_raccordement" in Variables_score:
                    if etudiant in Variables_score["ecarts_raccordement"]:
                        if colleur in Variables_score["ecarts_raccordement"][etudiant]:
                            if "up" in Variables_score["ecarts_raccordement"][etudiant][colleur]:
                                for couple in Variables_score["ecarts_raccordement"][etudiant][colleur]["up"]:
                                    for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple]:
                                        L.append(Variables_score["ecarts_raccordement"][etudiant][colleur]["up"][couple][start])
                Equations["sommes_scores"][etudiant][colleur]["up"].append(model.addConstr(VarUp<=gp.quicksum(L),name='equation_somme_scores_up'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["up"].append(model.addConstr(VarUp>=gp.quicksum(L)-(1-a)*M,name='equation_somme_scores_up'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["up"].append(model.addConstr(VarUp>=0,name='equation_somme_scores_up'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["up"].append(model.addConstr(VarUp<=a*M,name='equation_somme_scores_up'+etudiant.nom+'_'+colleur.nom))
                L=[]
                for couple in Variables_score['ecarts'][etudiant][colleur]["down"]:
                    for start in Variables_score['ecarts'][etudiant][colleur]["down"][couple]:
                        L.append(Variables_score['ecarts'][etudiant][colleur]["down"][couple][start])
                if "ecarts_raccordement" in Variables_score:
                    if etudiant in Variables_score["ecarts_raccordement"]:
                        if colleur in Variables_score["ecarts_raccordement"][etudiant]:
                            if "down" in Variables_score["ecarts_raccordement"][etudiant][colleur]:
                                for couple in Variables_score["ecarts_raccordement"][etudiant][colleur]["down"]:
                                    for start in Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple]:
                                        L.append(Variables_score["ecarts_raccordement"][etudiant][colleur]["down"][couple][start])
                Equations["sommes_scores"][etudiant][colleur]["down"].append(model.addConstr(Vardown<=gp.quicksum(L),name='equation_somme_scores_down'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["down"].append(model.addConstr(Vardown>=gp.quicksum(L)-a*M,name='equation_somme_scores_down'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["down"].append(model.addConstr(Vardown>=0,name='equation_somme_scores_down'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["down"].append(model.addConstr(Vardown<=(1-a)*M,name='equation_somme_scores_down'+etudiant.nom+'_'+colleur.nom))
                Equations["sommes_scores"][etudiant][colleur]["tot"]=model.addConstr(VarTot==VarUp+Vardown,name='equation_somme_scores_'+etudiant.nom+'_'+colleur.nom)

# %% Sauvegarde/chargement xml des solutions

def save_solution_to_xml(Variables, output_file):
    planning_elem = ET.Element("Planning")

    for semaine, etu_dict in Variables.items():
        semaine_elem = ET.SubElement(planning_elem, "Semaine", attrib={"numero": str(semaine)})
        for etu, activites in etu_dict.items():
            etu_elem = ET.SubElement(semaine_elem, "Etudiant", attrib={"id": etu.id})

            colle_elem = ET.SubElement(etu_elem, "Colle")
            tp_elem = ET.SubElement(etu_elem, "TP")

            for key in activites:
                sous_dict = activites[key]

                # Cas TP : sous_dict = {horaire: var}
                if isinstance(key, TP):  # ou autre test plus robuste
                    for h, var in sous_dict.items():
                        if var.X >= 0.5:
                            ET.SubElement(tp_elem, "TPElement", attrib={
                                "id": key.id,
                                "horaire": h.id
                            })

                # Cas colles : sous_dict = {colleur: {horaire: var}}
                else:  # c’est une matière
                    for col, horaires in sous_dict.items():
                        for h, var in horaires.items():
                            if var.X >= 0.5:
                                ET.SubElement(colle_elem, "Matiere", attrib={
                                    "id": key.id,
                                    "colleur": col.id,
                                    "horaire": h.id
                                })

    # Sauvegarde
    tree = ET.ElementTree(planning_elem)
    tree.write(output_file, encoding="utf-8", xml_declaration=True)
    print(f"Solution enregistrée dans {output_file}")

def load_solution_from_xml(xml_file, db):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    resultats = {}  # semaine → { etudiant → [ (matiere, colleur, horaire), ... ] + [(TP, None, horaire)] }

    for semaine_elem in root.findall("Semaine"):
        num_semaine = int(semaine_elem.attrib["numero"])
        resultats[num_semaine] = {}

        for etu_elem in semaine_elem.findall("Etudiant"):
            etu_id = etu_elem.attrib["id"]
            etu = db["etudiants"][etu_id]

            affectations = []

            colle_elem = etu_elem.find("Colle")
            if colle_elem is not None:
                for m_elem in colle_elem.findall("Matiere"):
                    mat = db["matieres"][m_elem.attrib["id"]]
                    col = db["colleurs"][m_elem.attrib["colleur"]]
                    hor = db["horaires"][m_elem.attrib["horaire"]]
                    affectations.append((mat, col, hor))

            tp_elem = etu_elem.find("TP")
            if tp_elem is not None:
                for t_elem in tp_elem.findall("TPElement"):
                    tp = db["TPs"][t_elem.attrib["id"]]
                    hor = db["horaires"][t_elem.attrib["horaire"]]
                    affectations.append((tp, None, hor))

            resultats[num_semaine][etu] = affectations


    return resultats

def load_solution_from_xml_id(xml_file,db):
    tree = ET.parse(xml_file)
    root = tree.getroot()

    resultats = {}  # semaine → { etudiant → [ (matiere, colleur, horaire), ... ] + [(TP, None, horaire)] }

    for semaine_elem in root.findall("Semaine"):
        num_semaine = int(semaine_elem.attrib["numero"])
        resultats[num_semaine] = {}

        for etu_elem in semaine_elem.findall("Etudiant"):
            etu_id = etu_elem.attrib["id"]


            affectations = []

            colle_elem = etu_elem.find("Colle")
            if colle_elem is not None:
                for m_elem in colle_elem.findall("Matiere"):
                    mat_id = m_elem.attrib["id"]
                    col_id = m_elem.attrib["colleur"]
                    hor_id = m_elem.attrib["horaire"]
                    affectations.append((mat_id, col_id, hor_id))

            tp_elem = etu_elem.find("TP")
            if tp_elem is not None:
                for t_elem in tp_elem.findall("TPElement"):
                    tp_id = t_elem.attrib["id"]
                    hor_id = t_elem.attrib["horaire"]
                    affectations.append((tp_id, None, hor_id))

            resultats[num_semaine][etu_id] = affectations


    return resultats


def load_planning_raccordement(resultats,db):
    """
    Cree le dictionnaire planning_a_raccorder utilisé dans les variables de score de raccordement
    Utilise le dictionnaire resultats généré par la fonction load_solution_from_xml_id (flemme de tout changer dans le fichier edition, mais c'est aussi la fonction qu'il faudrait utiliser dans le fichier edition si on veut faire ça proprement)
    """
    planning_a_raccorder={}
    planning_a_raccorder['semaines']=sorted([s for s in resultats])
    planning_a_raccorder['matieres_etudiant']={}
    planning_a_raccorder['colleurs_etudiant']={}
    for s in resultats:
        for etu_id in resultats[s]:
            if etu_id in db['etudiants']:
                etu=db['etudiants'][etu_id]
                if etu not in planning_a_raccorder['matieres_etudiant']:
                    planning_a_raccorder['matieres_etudiant'][etu]={}
                if etu not in planning_a_raccorder['colleurs_etudiant']:
                    planning_a_raccorder['colleurs_etudiant'][etu]={}
                for mat in etu.classe.matieres:
                    if set(mat.options).intersection(etu.options):
                        if mat not in planning_a_raccorder['matieres_etudiant'][etu]:
                            planning_a_raccorder['matieres_etudiant'][etu][mat]={}
                        planning_a_raccorder['matieres_etudiant'][etu][mat][s]=0
                        for col in mat.colleurs:
                            if col not in planning_a_raccorder['colleurs_etudiant'][etu]:
                                planning_a_raccorder['colleurs_etudiant'][etu][col]={}
                            planning_a_raccorder['colleurs_etudiant'][etu][col][s]=0
                for aff in resultats[s][etu_id]:
                    if aff[1]:
                        mat_id=aff[0]
                        col_id=aff[1]
                        if mat_id in db['matieres'] and col_id in db['colleurs']:
                            mat=db['matieres'][mat_id]
                            col=db['colleurs'][col_id]
                            if set(mat.options).intersection(etu.options):
                                planning_a_raccorder['matieres_etudiant'][etu][mat][s]=1
                                planning_a_raccorder['colleurs_etudiant'][etu][col][s]=1
    return planning_a_raccorder

##%Construction du modele

def build_model(db,planning_a_raccorder=None):
    """
    Construit le modele
    """
    Classes=db['classes'].values()
    Colleurs=db['colleurs'].values()
    model=creer_modele('Colloscope')
    Variables={}
    for cl in Classes:
        for semaine in cl.semaines_colles:
            ajout_variables_colles(semaine,cl,model,Variables)
            ajout_variables_TP(semaine,cl,model,Variables)
    Variables_aux={}
    ajout_variables_auxiliaires_debut_periode(model,Variables_aux,Classes)
    ajout_variables_auxiliaires_occupation_creneaux(model,Variables_aux,Colleurs)
    print('creation variables ok')
    Variables_score={}
    if planning_a_raccorder:
        ajout_variables_raccordement(model,Variables_score,Classes,planning_a_raccorder) #Attention a raccorder au depart
    ajout_variables_score(model,Variables_score,Classes)
    Equations={}
    equations_groupes(model,Variables,Classes,Equations)
    print('equations groupes OK')
    equations_somme_colles(model,Variables,Variables_aux,Classes,Equations)
    equations_debut_periodes(model,Variables,Variables_aux,Classes,Equations)
    if planning_a_raccorder:
        equations_alternance_matieres_TP(model,Variables,Variables_aux,Classes,Equations,planning_a_raccorder) #Penser a ajouter le planning a raccorder pour prendre en compte le nb max de colles
    else:
        equations_alternance_matieres_TP(model,Variables,Variables_aux,Classes,Equations)
    equations_matieres_groupees(model,Variables_aux,Classes,Equations)
    print('equations alternances matieres OK')
    equation_overlaps(model,Variables,Classes,Equations)
    print('equations overlaps OK')
    equations_occupation_creneaux(model,Variables,Variables_aux,Equations,Colleurs)
    equations_horaires_non_entiers(model,Variables,Variables_aux,Equations,Classes)
    print('equations horaires non entiers OK')
    equations_nombre_max_colles_etudiant(model,Variables,Equations)
    print('equations nombre de colles max ok')
    equations_places_TP_colles(model,Variables,Classes,Equations)
    print('equations places en colles OK')
    equations_heures(model,Variables_aux,Equations)
    #equations_colleurs_multi_classes(model,Variables_aux,Equations) # A debugger
    print("equations heures ok")
    equations_score(model,Variables,Variables_score,Variables_aux,Equations)
    if planning_a_raccorder:
        equations_score_raccordement_ecarts(model,Variables,Variables_score,Variables_aux,Equations,planning_a_raccorder)
        equations_raccordement_periodes(model,Variables_aux,Variables_score,Equations,planning_a_raccorder)
    equations_sommes_scores(model,Variables_score,Equations)
    print('equations de score ok')
    return model,Variables



if __name__=='__main__':
    db_base=load_all("PCSI_Test.xml")
    db=load_all("PCSI_Test - Extension.xml")
    Classes=db['classes'].values()
    Colleurs=db['colleurs'].values()
    resultats=load_solution_from_xml_id("Test_solution.xml",db_base)
    planning_a_raccorder=load_planning_raccordement(resultats,db)
    model,Variables=build_model(db,planning_a_raccorder)

    model.Params.TimeLimit = 3600
    model.Params.MIPGap = 0.01
    model.Params.MIPFocus = 2
    model.optimize()
    status = model.Status
    if status == GRB.Status.INFEASIBLE:
        model.computeIIS()
        for c in model.getConstrs():
            if c.IISConstr:
                print(f"Contrainte contradictoire : {c.ConstrName}")
    save_solution_to_xml(Variables,"Test_solution_raccordement.xml")


