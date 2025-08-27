import tkinter as tk
from tkinter import messagebox, filedialog, ttk
from classesColloscopeAuto import *
from datetime import date,timedelta
from tkcalendar import Calendar, DateEntry
from math import ceil,gcd
import csv
from functools import reduce
import threading
import time
import gurobipy as gp
from gurobipy import GRB
from pathlib import Path
from edition import *


#%% Fonctions utilitaires et classes


class ApplicationState:
    def __init__(self):
        self.db = {
            'calendrier': None,
            'colleurs': {},
            'classes': {},
            'etudiants': {},
            'matieres': {},
            'TPs': {},
            'horaires': {},
        }
        self.planning_a_raccorder=None
        self.fichier_nom = None  # Chaîne de caractères du type "monfichier.xml"
        self.help_text=''
        self.id=0
        self.rep_sauvegarde=None
        self.grb_state = {
            "model": None,
            "Variables": None,
            "thread": None,
            "running": False,
            "start_ts": None,
        }


def quitter_et_sauvegarder(app, fenetre):
    try:
        save_all(app.db, app.fichier_nom)
        print(f"Fichier {app.fichier_nom} sauvegardé.")
    except Exception as e:
        messagebox.showerror("Erreur", f"Sauvegarde échouée : {e}")
    finally:
        fenetre.destroy()
        nouvelle_app = ApplicationState()
        fenetre_accueil(root,nouvelle_app)
        root.deiconify()

def mettre_a_jour_aide(app):
    app.aide_widget.config(state="normal")
    app.aide_widget.delete("1.0", "end")
    app.aide_widget.insert("1.0", app.help_text)
    app.aide_widget.config(state="disabled")

def choisir_date(entry_widget):
    def valider_date():
        entry_widget.delete(0, tk.END)
        entry_widget.insert(0, cal.get_date())
        top.destroy()

    top = tk.Toplevel()
    top.grab_set()  # bloque les autres fenêtres
    cal = Calendar(top, date_pattern="yyyy-mm-dd")
    cal.pack(pady=10)
    tk.Button(top, text="OK", command=valider_date).pack(pady=5)

def ajouter_option(frame, entry_list):
    e = tk.Entry(frame)
    e.pack(fill="x", pady=2)
    entry_list.append(e)

def ppcm(a, b):
    return abs(a * b) // gcd(a, b) if a and b else 0

def ppcm_liste(lst):
    return reduce(ppcm, lst, 1)

#%% Gestion fenêtre accueil

def quitter():
    root.destroy()


def fenetre_accueil(root,app):
    """
    Creation de la fenetre d'accueil
    """
    root.title("Colloscope - Menu principal")
    root.geometry("480x220")  # largeur augmentée
    #root.resizable(False, False)
    root.grid_columnconfigure(0, weight=1)
    root.grid_columnconfigure(1, weight=1)
    root.grid_rowconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    root.grid_rowconfigure(2, weight=1)
    root.grid_rowconfigure(3, weight=1)

    # Titre visuel
    label = tk.Label(root, text="Bienvenue dans l'éditeur de colloscope", font=("Helvetica", 14))
    label.grid(row=0,column=0,columnspan=2,padx=20,pady=20,sticky='nsew')

    # Boutons
    btn_editer = tk.Button(root, text="Éditer un fichier existant", command=lambda : editer_fichier(app), width=30)
    btn_editer.grid(row=1,column=0,padx=5,pady=5,sticky='nsew')

    btn_creer = tk.Button(root, text="Créer un nouveau fichier", command=lambda:creer_fichier(app), width=30)
    btn_creer.grid(row=2,column=0,padx=5,pady=5,sticky='nsew')

    btn_quitter = tk.Button(root, text="Quitter", command=quitter, width=30)
    btn_quitter.grid(row=3,column=0,columnspan=2,padx=20,pady=20,sticky='nsew')

    btn_resolution=tk.Button(root, text="Lancer une résolution", command=lambda : vers_resolution(app), width=30)
    btn_resolution.grid(row=1,column=1,padx=5,pady=5,sticky='nsew')

    btn_raccordement=tk.Button(root, text="Etendre un colloscope existant", command=lambda : vers_raccordement(app), width=30)
    btn_raccordement.grid(row=2,column=1,padx=5,pady=5,sticky='nsew')



def editer_fichier(app):
    chemin = filedialog.askopenfilename(
        title="Choisir un fichier XML existant",
        filetypes=[("Fichiers XML", "*.xml")],
        defaultextension=".xml"
    )
    if not chemin:
        return  # L'utilisateur a annulé

    try:
        app.db = load_all(chemin)
        max_id = 0

        for cle in app.db:
            dic_objets = app.db[cle]
            if isinstance(dic_objets, dict):
                for obj_id in dic_objets:
                    try:
                        max_id = max(max_id, int(obj_id))
                    except ValueError:
                        pass  # si un ID n'est pas un entier (par exemple "vacances"), on l'ignore

        app.id = max_id + 1
        app.fichier_nom = chemin


        ouvrir_fenetre_edition(app)
        root.withdraw()
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec du chargement du fichier :\n{e}")

def creer_fichier(app):
    # Ouvre une boîte de dialogue pour choisir le nom et le chemin du fichier
    chemin = filedialog.asksaveasfilename(
        defaultextension=".xml",
        filetypes=[("Fichier XML", "*.xml")],
        title="Créer un nouveau fichier XML"
    )

    if not chemin:
        return  # L'utilisateur a annulé

    if not chemin.endswith(".xml"):
        chemin += ".xml"

    # Initialise la base de données vide
    app.db = {
        'calendrier': None,
        'classes': {},
        'etudiants': {},
        'matieres': {},
        'TP': {},
        'colleurs': {},
        'horaires': {},
        'resultats': {}
    }

    # Met à jour le nom complet du fichier
    app.fichier_nom = chemin

    # Ouvre la fenêtre d'édition
    ouvrir_fenetre_edition(app)

#%% Gestion fenêtre lancement resolution

def vers_resolution(app):
    chemin = filedialog.askopenfilename(
        title="Choisir le fichier XML pour la résolution",
        filetypes=[("Fichiers XML", "*.xml")],
        defaultextension=".xml"
    )
    if not chemin:
        return  # L'utilisateur a annulé

    chemin_sauvegarde = filedialog.askdirectory(
        title="Choisir l'emplacement des fichiers de résultats"
    )
    if not chemin_sauvegarde:
        return

    try:
        app.db = load_all(chemin)
        app.fichier_nom = chemin
        app.rep_sauvegarde=chemin_sauvegarde
        ouvrir_fenetre_resolution(app)
        root.withdraw()
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec du chargement du fichier :\n{e}")

def vers_raccordement(app):
    chemin = filedialog.askopenfilename(
        title="Choisir le fichier XML de paramétrage pour la résolution",
        filetypes=[("Fichiers XML", "*.xml")],
        defaultextension=".xml"
    )
    if not chemin:
        return  # L'utilisateur a annulé

    chemin_raccordement = filedialog.askopenfilename(
        title="Choisir le fichier XML solution à étendre (solution a raccorder)",
        filetypes=[("Fichiers XML", "*.xml")],
        defaultextension=".xml"
    )
    if not chemin_raccordement:
        return  # L'utilisateur a annulé

    chemin_base = filedialog.askopenfilename(
        title="Choisir le fichier XML de paramétrage dont vient la solution à raccorder",
        filetypes=[("Fichiers XML", "*.xml")],
        defaultextension=".xml"
    )
    if not chemin_base:
        return  # L'utilisateur a annulé

    chemin_sauvegarde = filedialog.askdirectory(
        title="Choisir l'emplacement des fichiers de résultats"
    )
    if not chemin_sauvegarde:
        return

    try:
        app.db = load_all(chemin)
        app.fichier_nom = chemin
        db_base=load_all(chemin_base)
        resultats=load_solution_from_xml_id(chemin_raccordement,db_base)
        app.planning_a_raccorder=load_planning_raccordement(resultats,app.db)
        app.rep_sauvegarde=chemin_sauvegarde
        ouvrir_fenetre_resolution(app)
        root.withdraw()
    except Exception as e:
        messagebox.showerror("Erreur", f"Échec du chargement du fichier :\n{e}")


def ouvrir_fenetre_resolution(app):
    root.withdraw()
    fen = tk.Toplevel()
    fen.title("Résolution")
    fen.geometry("1200x800")

    fen.protocol("WM_DELETE_WINDOW", lambda: quitter_et_sauvegarder(app, fen))

    frm = ttk.Frame(fen, padding=10)
    frm.grid(row=0, column=0, sticky="nsew")

    fen.rowconfigure(0, weight=1)
    fen.columnconfigure(0, weight=1)

    #Fonctions


    def log(msg):
        txt.insert("end", msg + "\n")
        txt.see("end")

    def start():
        if app.grb_state["running"]:
            log("Déjà en cours."); return
        try:
            m, Variables = build_model(app.db,app.planning_a_raccorder)
        except Exception as e:
            messagebox.showerror("Erreur build_model", str(e))
            return

        # Lire les paramètres saisis par l'utilisateur (si fournis)
        try:
            tl_raw = entry_timelimit.get().strip()
            gl_raw = entry_gaplimit.get().strip()

            if tl_raw:
                tl = parse_time_limit(tl_raw)
                if tl is not None and tl >= 0:
                    m.Params.TimeLimit = tl
                    log(f"TimeLimit appliqué : {tl:.1f} s")

            if gl_raw:
                gl = parse_gap_limit(gl_raw)
                if gl is not None and gl >= 0:
                    m.Params.MIPGap = gl
                    log(f"MIPGap appliqué : {gl:.4f} ({100*gl:.2f}%)")
        except Exception as e:
            messagebox.showerror("Paramètres invalides", f"{e}")
            return

        app.grb_state.update({
            "model": m,
            "Variables": Variables,
            "running": True,
            "start_ts": time.time(),
        })
        btn_start.config(state="disabled")
        btn_stop.config(state="normal")
        log("Optimisation lancée…")

        def run():
            try:
                m.optimize()
                # À la fin / après terminate / time limit : sauvegarde si solution
                if m.SolCount > 0:
                    nom_fichier=Path(app.fichier_nom).stem
                    chemin_sauvegarde = Path(app.rep_sauvegarde) / f"{nom_fichier}_solution.xml"
                    save_solution_to_xml(Variables, chemin_sauvegarde)
                    resultats=load_solution_from_xml(chemin_sauvegarde,app.db)
                    export_resultats_pdf(Path(app.rep_sauvegarde) / "Resultats_pdf",resultats,app.db)
                    export_resultats_html_json(resultats, app.db, Path(app.rep_sauvegarde) / "affichage_interactif")
                    export_resultats_groupes_xlsx(resultats,app.db,app.db['calendrier'],chemin_sauvegarde.with_suffix(".xlsx"))
                    log(f"Solution courante sauvegardée dans {app.rep_sauvegarde}")
                # Récap utile
                try:
                    STATUS_NAMES = {
                        GRB.Status.LOADED: "LOADED",
                        GRB.Status.OPTIMAL: "OPTIMAL",
                        GRB.Status.INFEASIBLE: "INFEASIBLE",
                        GRB.Status.INF_OR_UNBD: "INF_OR_UNBD",
                        GRB.Status.UNBOUNDED: "UNBOUNDED",
                        GRB.Status.CUTOFF: "CUTOFF",
                        GRB.Status.ITERATION_LIMIT: "ITERATION_LIMIT",
                        GRB.Status.NODE_LIMIT: "NODE_LIMIT",
                        GRB.Status.TIME_LIMIT: "TIME_LIMIT",
                        GRB.Status.SOLUTION_LIMIT: "SOLUTION_LIMIT",
                        GRB.Status.INTERRUPTED: "INTERRUPTED",
                    }
                    status_name = STATUS_NAMES.get(m.Status, f"UNKNOWN({m.Status})")
                    log(f"Status final : {status_name} ({m.Status})")
                    if m.SolCount > 0:
                        log(f"Incumbent ObjVal : {m.ObjVal:.4f}")
                    log(f"BestBd (ObjBound) : {m.ObjBound:.4f}")
                    if m.SolCount > 0:
                        log(f"Gap : {100*m.MIPGap:.2f}%")
                except gp.GurobiError:
                    pass
            except Exception as e:

                log(f"Erreur pendant optimize() : {e}")
            finally:
                app.grb_state["running"] = False
                fen.after(0, lambda: (btn_start.config(state="normal"),
                                    btn_stop.config(state="disabled")))

        t = threading.Thread(target=run, daemon=True)
        app.grb_state["thread"] = t
        t.start()

    def stop():
        if app.grb_state["running"] and app.grb_state["model"] is not None:
            try:
                app.grb_state["model"].terminate()
                log("Arrêt demandé (terminate).")
            except Exception as e:
                log(f"Impossible d'arrêter proprement : {e}")
        else:
            log("Rien à arrêter.")


    def tick_elapsed():
        if app.grb_state["running"] and app.grb_state["start_ts"]:
            elapsed = time.time() - app.grb_state["start_ts"]
            lbl_time.config(text=f"Temps écoulé : {elapsed:,.1f} s")

        root.after(200, tick_elapsed)


    def parse_time_limit(s: str):
        """Accepte '3600' (sec) ou 'HH:MM:SS' (p.ex. '01:30:00'). Retourne secondes (float)."""
        s = s.strip()
        if not s:
            return None
        if ":" in s:
            parts = s.split(":")
            if len(parts) != 3:
                raise ValueError("Format attendu HH:MM:SS")
            h, m, sec = [float(p.replace(",", ".")) for p in parts]
            return 3600*h + 60*m + sec
        # sinon: secondes
        return float(s.replace(",", "."))

    def parse_gap_limit(s: str):
        """Accepte '0.01' (1%) ou '1%' (1 pourcent). Retourne fraction (ex. 0.01)."""
        s = s.strip()
        if not s:
            return None
        s = s.replace(",", ".")
        if s.endswith("%"):
            v = float(s[:-1])
            return v / 100.0
        v = float(s)
        # Si l'utilisateur met 1.0 et voulait 1%, il peut aussi écrire '1%'
        return v


    # Ligne paramètres
    params = ttk.Frame(frm); params.grid(row=0, column=0, sticky="w", pady=(0,8))

    ttk.Label(params, text="Limite de temps (sec ou HH:MM:SS) :").grid(row=0, column=0, sticky="w")
    entry_timelimit = ttk.Entry(params, width=12)
    entry_timelimit.grid(row=0, column=1, padx=(4,12))
    ttk.Label(params, text="(à laisser vide si vous n'êtes pas pressé)").grid(row=0, column=2, sticky="w")

    ttk.Label(params, text="Limite du Gap (écart relatif entre Meilleure Solution trouvée et théorique, à laisser vide si vous voulez la meilleure solution possible) :").grid(row=1, column=0, sticky="w", padx=(16,0))
    entry_gaplimit = ttk.Entry(params, width=10)
    entry_gaplimit.grid(row=1, column=1, padx=(4,6))
    ttk.Label(params, text="(ex: 0.01 ou 1%)").grid(row=1, column=2, sticky="w")

    # Boutons
    btns = ttk.Frame(frm); btns.grid(row=2, column=0, sticky="w")
    btn_start = ttk.Button(btns, text="Lancer la résolution", command=start)
    btn_stop  = ttk.Button(btns, text="Arrêter", command=stop, state="disabled")
    btn_start.grid(row=0, column=0, padx=(0,8))
    btn_stop.grid(row=0, column=1)

    lbl_time = ttk.Label(frm, text="Temps écoulé : 0.0 s")
    lbl_time.grid(row=3, column=0, pady=(8,4), sticky="w")

    txt = tk.Text(frm)
    txt.grid(row=4, column=0, pady=(8,0), sticky="nsew")
    frm.rowconfigure(4, weight=1); frm.columnconfigure(0, weight=1)

    tick_elapsed()

#%% Gestion fenêtre edition

def ouvrir_fenetre_edition(app):
    root.withdraw()
    fen = tk.Toplevel()
    fen.title("Édition du planning")
    fen.geometry("1200x800")


    # Bonnes proportions
    fen.grid_columnconfigure(0, weight=1,minsize=600)
    fen.grid_columnconfigure(1, weight=1,minsize=600)
    fen.grid_rowconfigure(0, weight=1,minsize=600)  # Haut
    fen.grid_rowconfigure(1, weight=1,minsize=200)   # Bas

    fen.protocol("WM_DELETE_WINDOW", lambda: quitter_et_sauvegarder(app, fen))

    # ====================
    # 1. Cadre gauche + scroll avec Canvas
    # ====================
    cadre_gauche = tk.Frame(fen)
    cadre_gauche.grid(row=0, column=0, sticky="nsew")
    cadre_gauche.grid_rowconfigure(0, weight=1)
    cadre_gauche.grid_columnconfigure(0, weight=1)

    scrollbar = tk.Scrollbar(cadre_gauche)
    scrollbar.grid(row=0, column=1, sticky="ns")

    treeview = ttk.Treeview(cadre_gauche, yscrollcommand=scrollbar.set)
    treeview.grid(row=0, column=0, sticky="nsew")
    scrollbar.config(command=treeview.yview)

    # Remplir le treeview
    construire_arborescence_gauche(treeview, app)

    # ====================
    # 1bis. Bouton valider en bas du cadre gauche
    # ====================
    bouton_valider = tk.Button(cadre_gauche, text="Valider le paramétrage", command=lambda: quitter_et_sauvegarder(app, fen))
    bouton_valider.grid(row=1, column=0, columnspan=2, sticky="e", padx=10, pady=10)
    construire_arborescence_gauche(treeview, app)


    # ====================
    # 2. Cadre haut droite + scroll
    # ====================
    frame_haut_droite = tk.Frame(fen)
    frame_haut_droite.grid(row=0, column=1,sticky="nsew")
    #frame_haut_droite.grid_propagate(False)  # empêche le redimensionnement interne

    frame_haut_droite.grid_rowconfigure(0, weight=1)
    frame_haut_droite.grid_columnconfigure(0, weight=1)

    canvas_haut = tk.Canvas(frame_haut_droite)
    scrollbar_haut = tk.Scrollbar(frame_haut_droite, orient="vertical", command=canvas_haut.yview)
    inner_haut = tk.Frame(canvas_haut)

    inner_haut.bind("<Configure>", lambda e: canvas_haut.configure(scrollregion=canvas_haut.bbox("all")))
    canvas_haut.create_window((0, 0), window=inner_haut, anchor="nw")
    canvas_haut.configure(yscrollcommand=scrollbar_haut.set)

    canvas_haut.grid(row=0, column=0, sticky="nsew")
    scrollbar_haut.grid(row=0, column=1, sticky="ns")



    # ====================
    # 3. Cadre bas droite + scroll
    # ====================
    frame_bas_droite = tk.Frame(fen, bg="#e6f0ff")
    frame_bas_droite.grid(row=1, column=0, columnspan=2, sticky="nsew")

    #frame_bas_droite.grid_propagate(False)  #  idem pour forcer la taille

    frame_bas_droite.grid_rowconfigure(0, weight=1)
    frame_bas_droite.grid_columnconfigure(0, weight=1)

    canvas_bas = tk.Canvas(frame_bas_droite, bg="#e6f0ff", highlightthickness=0)
    canvas_bas.grid(row=0, column=0, sticky="nsew")

    scrollbar_bas = tk.Scrollbar(frame_bas_droite, orient="vertical", command=canvas_bas.yview)
    scrollbar_bas.grid(row=0, column=1, sticky="ns")

    # Cadre interne qui contiendra l’aide
    inner_bas = tk.Frame(canvas_bas, bg="#e6f0ff")
    canvas_window = canvas_bas.create_window((0, 0), window=inner_bas, anchor="nw")

    canvas_bas.configure(yscrollcommand=scrollbar_bas.set)

    #  Pour que le canvas suive la taille du contenu
    def _on_configure(event):
        canvas_bas.configure(scrollregion=canvas_bas.bbox("all"))
    inner_bas.bind("<Configure>", _on_configure)

    # Configuration du cadre interne
    inner_bas.grid_rowconfigure(1, weight=1)
    inner_bas.grid_columnconfigure(0, weight=1)

    # Icône ❓
    icone = tk.Label(inner_bas, text="❓", font=("Arial", 16), bg="#e6f0ff")
    icone.grid(row=0, column=0, sticky="nw", padx=5, pady=(5, 0))

    # Zone de texte
    app.aide_widget = tk.Text(inner_bas, wrap="word",width=80, state="normal", bg="#e6f0ff", relief="flat", bd=0)
    app.aide_widget.insert("1.0", app.help_text)
    app.aide_widget.config(state="disabled")
    app.aide_widget.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)

    # Lié à la taille du canvas
    def resize_text_widget(event):
        canvas_bas.itemconfig(canvas_window, width=event.width)

    canvas_bas.bind("<Configure>", resize_text_widget)

    # Lien sélection arbre -> formulaire
    treeview.bind("<<TreeviewSelect>>", lambda event: on_treeview_select(event, app, inner_haut, treeview))

    # Stockage dans l'app si besoin plus tard
    app._fenetre_edition = fen
    app._cadres_edition = {
        "gauche": cadre_gauche,
        "haut": inner_haut,
        "bas": inner_bas
    }

#%% Affichage dynamique Treeview Cadre Gauche

def construire_arborescence_gauche(treeview, app):
    # Étape 1 : sauvegarder les items ouverts
    opened_items = set()

    def save_open_state(item):
        if treeview.item(item, 'open'):
            opened_items.add(item)
        for child in treeview.get_children(item):
            save_open_state(child)

    for root in treeview.get_children():
        save_open_state(root)

    # Étape 2 : vider l'arborescence
    for item in treeview.get_children():
        treeview.delete(item)

    # Étape 3 : reconstruire l'arborescence

    # Racine 1 : Calendrier
    calendrier_id = treeview.insert("", "end", iid="Calendrier", text="Calendrier", open=True)

    if app.db['calendrier']:
        # Racine 2 : Classes
        classes_id = treeview.insert("", "end", iid='Classes', text="Classes", open=True)

        for cls_id, cls in app.db.get("classes", {}).items():
            classe_node = treeview.insert(classes_id, "end", iid="classe" + cls_id, text=cls.nom, open=False)

            # Sous-éléments de la classe
            treeview.insert(classe_node, "end", iid=f"{cls_id}_matieres", text="Matières")
            treeview.insert(classe_node, "end", iid=f"{cls_id}_tp", text="TP/TD")
            tp_node_id = f"{cls_id}_tp"
            for tp in cls.TP:
                tp_iid = f"tp_{cls_id}_{tp.id}"
                treeview.insert(tp_node_id, "end", iid=tp_iid, text=tp.nom)
                tp_horaires_node = treeview.insert(tp_iid, "end", iid=f"{tp_iid}_horaires", text="Horaires")
                for i,h in enumerate(tp.horaires):
                    treeview.insert(tp_horaires_node, "end", iid=f"{tp_iid}_horaire_{h.id}", text=f"{h.jour} {h.debut//60:02}:{h.debut%60:02}")
            treeview.insert(classe_node, "end", iid=f"{cls_id}_etudiants", text="Étudiants")
            etudiants_node_id = f"{cls_id}_etudiants"
            for etu in cls.etudiants:
                etu_iid = f"etudiant_{cls_id}_{etu.id}"
                treeview.insert(etudiants_node_id, "end", iid=etu_iid, text=etu.nom)
            treeview.insert(classe_node, "end", iid=f"{cls_id}_edt", text="Contraintes EDT par option")
            # Contraintes horaires par option
            edt_node = f"{cls_id}_edt"
            treeview.insert(edt_node, "end", iid=f"{cls_id}_edt_ajout", text="Horaires")
            horaire_edt_node=f"{cls_id}_edt_ajout"
            for i, h in enumerate(cls.edt):
                treeview.insert(horaire_edt_node, "end", iid=f"{cls_id}_edt_horaire_{h.id}", text=f"{h.jour} {h.debut//60:02}:{h.debut%60:02}")
            treeview.insert(classe_node, "end", iid=f"{cls_id}_groupes", text="Groupements de matières")

            groupes_id = f"{cls_id}_groupes"
            for (matieres_tuple, option), decalages in cls.matieres_groupees.items():
                noms_matieres = [m.nom for m in matieres_tuple]
                texte = f"({' + '.join(noms_matieres)}) [{option}]"
                iid_groupe = f"{cls_id}_grp_" + "_".join(m.id for m in matieres_tuple) + f"_{option}"
                treeview.insert(groupes_id, "end", iid=iid_groupe, text=texte)

        for mat_id, mat in app.db.get("matieres", {}).items():
            matiere_iid = f"{mat.classe.id}_matieres"
            matiere_node_id = f"matiere_{mat.classe.id}_{mat.id}"
            treeview.insert(matiere_iid, "end", iid=matiere_node_id, text=mat.nom, open=False)

            colleurs_node_id = f"{matiere_node_id}_colleurs"
            treeview.insert(matiere_node_id, "end", iid=colleurs_node_id, text="Colleurs", open=False)

            for colleur in mat.colleurs:
                colleur_iid = f"{matiere_node_id}_colleur_{colleur.id}"
                treeview.insert(colleurs_node_id, "end", iid=colleur_iid, text=colleur.nom)
                colleur_horaire_node = treeview.insert(colleur_iid, "end", iid=f"{colleur_iid}_horaires", text="Horaires")
                for i, h in enumerate(colleur.horaires):
                    treeview.insert(colleur_horaire_node, "end", iid=f"{colleur_iid}_horaire_{h.id}", text=f"{h.jour} {h.debut//60:02}:{h.debut%60:02}")

        # Étape 4 : rouvrir les items précédemment ouverts
        for iid in opened_items:
            if treeview.exists(iid):
                treeview.item(iid, open=True)





def on_treeview_select(event, app, inner_haut,treeview):
    selected = event.widget.selection()
    if not selected:
        return
    item = selected[0]


    # Exemple : clic sur "Classes"
    if item == "Classes":
        afficher_formulaire_ajout_classe(app, inner_haut, treeview)

    # Exemple : clic sur "Calendrier"
    elif item == "Calendrier":
        afficher_formulaire_calendrier(app, inner_haut, treeview)

    elif item.startswith("classe"):
            classe_id = item.replace("classe", "")
            afficher_formulaire_edition_classe(app, inner_haut, classe_id,treeview)

    elif "groupes" in item:
        classe_id=item.split("_")[0]
        afficher_formulaire_creation_groupe_matiere(app,inner_haut,treeview,classe_id)

    elif "_grp_" in item:
        classe_id = item.split("_")[0]
        afficher_formulaire_modification_groupe_matiere(app, inner_haut, treeview, classe_id, item)

    elif "matieres" in item:
        classe_id = item.split("_")[0]
        afficher_formulaire_ajout_matiere(app, inner_haut, treeview, classe_id)



    elif "_colleurs" in item and item.startswith("matiere_"):
            classe_id = item.split("_")[1]
            matiere_id = item.split("_")[2]
            afficher_formulaire_creation_colleur(app, inner_haut, treeview, matiere_id)



    elif item.startswith("etudiant_"):
        parts = item.split("_")
        classe_id = parts[1]
        etudiant_id = parts[2]
        afficher_formulaire_edition_etudiant(app, inner_haut, treeview, classe_id, etudiant_id)

    elif item.endswith("_etudiants"):
        classe_id = item.split("_")[0]
        afficher_formulaire_creation_etudiant(app, inner_haut, treeview, classe_id)

    elif "_horaire_" in item and item.startswith("tp_"):
        parts = item.split("_")
        classe_id = parts[1]
        tp_id = parts[2]
        h_id= parts[-1]
        tp = next((tp for tp in app.db["TPs"].values() if tp.id == tp_id), None)
        if tp:
            edition_horaire_tp(app, inner_haut, treeview, tp, app.db['horaires'][h_id])

    elif item.endswith("_horaires") and item.startswith("tp_"):
        parts = item.split("_")
        classe_id = parts[1]
        tp_id = parts[2]
        tp = next((tp for tp in app.db["TPs"].values() if tp.id == tp_id), None)
        if tp:
            creation_horaire_tp(app, inner_haut, treeview, tp)

    elif "_edt_horaire_" in item:
        classe_id = item.split("_")[0]
        index = item.split("_")[-1]
        cls = app.db["classes"][classe_id]
        edition_horaire_classe(app, inner_haut, treeview, cls, app.db['horaires'][index])

    elif item.endswith("_edt_ajout"):
        classe_id = item.split("_")[0]
        cls = app.db["classes"][classe_id]
        creation_horaire_classe(app, inner_haut, treeview, cls)


    elif "_horaire_" in item and "_colleur_" in item:
        parts = item.split("_")
        classe_id = parts[1]
        matiere_id = parts[2]
        colleur_id = parts[4]
        index = parts[-1]
        colleur = app.db["colleurs"][colleur_id]
        edition_horaire_colleur(app, inner_haut, treeview, colleur, app.db['horaires'][index],app.db['matieres'][matiere_id])

    elif item.endswith("_horaires") and "_colleur_" in item:
        parts = item.split("_")
        classe_id = parts[1]
        matiere_id = parts[2]
        colleur_id = parts[4]
        col = app.db["colleurs"][colleur_id]
        mat=app.db['matieres'][matiere_id]
        creation_horaire_colleur(app, inner_haut, treeview, col,mat)

    elif item.startswith("tp_"):
            parts = item.split("_")
            classe_id = parts[1]
            tp_id = parts[2]
            afficher_formulaire_edition_tp(app, inner_haut, treeview, classe_id, tp_id)

    elif "tp" in item:
        classe_id = item.split("_")[0]
        afficher_formulaire_creation_tp(app, inner_haut, treeview, classe_id)

    # Clic sur un colleur spécifique
    elif "_colleur_" in item and "matiere_" in item:
        parts = item.split("_")
        classe_id = parts[1]
        matiere_id = parts[2]
        colleur_id = parts[-1]
        afficher_formulaire_edition_colleur(app, inner_haut, treeview, matiere_id, colleur_id)


    elif item.startswith("matiere"):
        classe_id=item.split("_")[1]
        matiere_id=item.split("_")[2]
        afficher_formulaire_edition_matiere(app, inner_haut, treeview, classe_id, matiere_id)
#%% Formulaires cadre droit



def afficher_formulaire_ajout_classe(app, frame,treeview):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Ce formulaire vous permet d’ajouter une nouvelle classe.\n Les options vous permettent de gérer des alternances de colles, TP et/ou TD différenciés selon les élèves (option SI ou Chimie en PCSI par exemple, groupes d'informatique, etc) ou d'ajouter des contraintes spécifiques d'emploi du temps (LV2 par exemple). Par défaut, une option avec le nom de la classe sera créée automatiquement.\n Les semaines de colles sont à choisir parmi les semaines de cours, en utilisant la numérotation Pronote (semaines chômées non comptées)\n Enfin, l'option nombre de colles max par semaine sert à limiter le nombre de colles maximum qu'un étudiant peut avoir chaque semaine (à manier avec précaution, peut empêcher de trouver des solutions) "
    mettre_a_jour_aide(app)
    tk.Label(frame, text="Ajout d'une classe", font=("Arial", 14, "bold")).pack(pady=10)

    # Nom de la classe
    tk.Label(frame, text="Nom de la classe :").pack(anchor="w", padx=10)
    entry_nom = tk.Entry(frame)
    entry_nom.pack(fill="x", padx=10)

    # Options
    tk.Label(frame, text="Options supplémentaires :").pack(anchor="w", padx=10, pady=(10, 0))
    entry_option = tk.Entry(frame)
    entry_option.pack(fill="x", padx=10)

    options_listbox = tk.Listbox(frame, selectmode=tk.MULTIPLE, height=4)
    options_listbox.pack(fill="both", padx=10, pady=5)

    def ajouter_option():
        opt = entry_option.get().strip()
        if opt and opt not in options_listbox.get(0, tk.END):
            options_listbox.insert(tk.END, opt)
            entry_option.delete(0, tk.END)

    tk.Button(frame, text="Ajouter option", command=ajouter_option).pack(padx=10)

    # Semaines de colles
    tk.Label(frame, text="Choisissez les semaines de colles :").pack(anchor="w", padx=10, pady=(10, 0))

    semaines_frame = tk.Frame(frame)
    semaines_frame.pack(fill="both", padx=10, pady=5)

    dico_semaines = app.db['calendrier'].get_all_semaines()
    semaine_vars = {}

    for i, (num, (d, f)) in enumerate(dico_semaines.items()):
        var = tk.BooleanVar()
        semaine_vars[num] = var
        texte = f"Semaine {num} : du {d.strftime('%d/%m')} au {f.strftime('%d/%m')}"
        cb = tk.Checkbutton(semaines_frame, text=texte, variable=var)
        cb.grid(row=i // 2, column=i % 2, sticky="w")

    def toggle_semaines():
        all_checked = all(v.get() for v in semaine_vars.values())
        for v in semaine_vars.values():
            v.set(not all_checked)

    tk.Button(frame, text="Tout cocher / Tout décocher", command=toggle_semaines).pack(pady=(0, 10))

    # nbCollesMax
    tk.Label(frame, text="Nombre de colles max par semaine :").pack(anchor="w", padx=10, pady=(10, 0))
    entry_nbcolles = tk.Entry(frame)
    entry_nbcolles.insert(0, "10")
    entry_nbcolles.pack(fill="x", padx=10)

    def valider():
        nom = entry_nom.get().strip()
        try:
            nbcollesmax = int(entry_nbcolles.get())
        except ValueError:
            messagebox.showerror("Erreur", "Le nombre de colles max doit être un entier.")
            return

        if not nom:
            messagebox.showerror("Erreur", "Le nom de la classe est obligatoire.")
            return

        options = list(options_listbox.get(0, tk.END))
        if nom not in options:
            options.insert(0, nom)  # Ajoute en tête l'option par défaut liée à la classe

        semaines_colles = sorted([n for n, v in semaine_vars.items() if v.get()])
        semaines_cours = sorted(dico_semaines.keys())

        if not hasattr(app, "id"):
            app.id = 1

        new_classe = classe(
            id=str(app.id),
            nom=nom,
            etudiants=[],
            matieres=[],
            TP=[],
            options=options,
            semaines_colles=semaines_colles,
            semaines_cours=semaines_cours,
            edt=[],
            matieres_groupees={},
            nbCollesMax=nbcollesmax
        )

        app.db["classes"][str(app.id)] = new_classe
        app.id += 1


        construire_arborescence_gauche(treeview, app)

        messagebox.showinfo("Succès", f"Classe {nom} ajoutée.")
        afficher_formulaire_ajout_classe(app, frame,treeview)  # Réinitialise le formulaire

    tk.Button(frame, text="Ajouter la classe", command=valider).pack(pady=10)

def afficher_formulaire_calendrier(app, cadre, treeview):
    for widget in cadre.winfo_children():
        widget.destroy()

    app.help_text = "Permet d'éditer le calendrier. Une fois le calendrier validé, vous pourrez ajouter des classes.\n Pour les dates de vacances, vous pouvez recopier celles sur education.gouv.fr (fin le samedi, reprise le lundi) \n Les jours fériés sont ajoutés automatiquement, mais vous pouvez également en ajouter à la main si vous avez des journées banalisées (portes ouvertes, forums, etc)\n Si vous ajoutez les dates à la main, attention le format attendu est AAAA-MM-DD"
    mettre_a_jour_aide(app)

    if "calendrier" in app.db:
        cal = app.db['calendrier']
    else:
        cal = None

    from datetime import date

    frame_rentree = tk.Frame(cadre)
    frame_rentree.pack(fill="x", padx=10, pady=5)
    tk.Label(frame_rentree, text="Date de rentrée (AAAA-MM-JJ) :").pack(side="left")
    entry_rentree = tk.Entry(frame_rentree, width=12)
    if cal and cal.rentree:
        entry_rentree.insert(0, cal.rentree.strftime("%Y-%m-%d"))
    entry_rentree.pack(side="left", padx=2)
    btn_rentree = tk.Button(frame_rentree, text="📅", command=lambda: choisir_date(entry_rentree))
    btn_rentree.pack(side="left")

    frame_fin = tk.Frame(cadre)
    frame_fin.pack(fill="x", padx=10, pady=5)
    tk.Label(frame_fin, text="Date de fin d'année (AAAA-MM-JJ) :").pack(side="left")
    entry_fin = tk.Entry(frame_fin, width=12)
    if cal and cal.fin:
        entry_fin.insert(0, cal.fin.strftime("%Y-%m-%d"))
    entry_fin.pack(side="left", padx=2)
    btn_fin = tk.Button(frame_fin, text="📅", command=lambda: choisir_date(entry_fin))
    btn_fin.pack(side="left")

    vacances_labels = ["Toussaint", "Noël", "Hiver", "Printemps"]
    vacances_entries = {}

    frame_vacances = tk.Frame(cadre)
    frame_vacances.pack(fill="x", padx=10, pady=10)

    tk.Label(frame_vacances, text="Vacances (début et reprise)").grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 5))

    for i, nom in enumerate(vacances_labels, start=1):
        tk.Label(frame_vacances, text=nom + " :").grid(row=i, column=0, sticky="e", padx=5, pady=2)
        e_debut = tk.Entry(frame_vacances, width=12)
        e_reprise = tk.Entry(frame_vacances, width=12)
        if cal and cal.vacances and nom in cal.vacances:
            e_debut.insert(0, cal.vacances[nom][0].strftime("%Y-%m-%d"))
            e_reprise.insert(0, cal.vacances[nom][1].strftime("%Y-%m-%d"))
        b_debut = tk.Button(frame_vacances, text="📅", command=lambda e=e_debut: choisir_date(e))
        b_reprise = tk.Button(frame_vacances, text="📅", command=lambda e=e_reprise: choisir_date(e))

        e_debut.grid(row=i, column=1, padx=2)
        b_debut.grid(row=i, column=2, padx=2)
        e_reprise.grid(row=i, column=3, padx=2)
        b_reprise.grid(row=i, column=4, padx=2)
        vacances_entries[nom] = (e_debut, e_reprise)

    # Jours chômés manuels
    jours_feries_widgets = []
    frame_jours = tk.LabelFrame(cadre, text="Autres jours chômés à ajouter manuellement")
    frame_jours.pack(fill="both", expand=True, padx=10, pady=10)

    def ajouter_jour_ferie(val=""):
        row = len(jours_feries_widgets)
        entry = tk.Entry(frame_jours, width=12)
        entry.grid(row=row, column=0, padx=2, pady=2, sticky="w")
        if val:
            entry.insert(0, val)

        btn_date = tk.Button(frame_jours, text="📅", command=lambda e=entry: choisir_date(e))
        btn_date.grid(row=row, column=1, padx=2, pady=2)

        def supprimer_jour_ferie():
            entry.destroy()
            btn_date.destroy()
            btn_suppr.destroy()
            try:
                jours_feries_widgets.remove((entry, btn_date, btn_suppr))
            except ValueError:
                pass

        btn_suppr = tk.Button(frame_jours, text="🗑️", command=supprimer_jour_ferie)
        btn_suppr.grid(row=row, column=2, padx=2, pady=2)

        jours_feries_widgets.append((entry, btn_date, btn_suppr))

    # Préremplir les jours manuels s'ils existent
    if cal and hasattr(cal, "jours_feries_manuel"):
        jours_manuels = sorted(set(cal.jours_feries_manuel))
        for j in jours_manuels:
            ajouter_jour_ferie(j.strftime("%Y-%m-%d"))

    tk.Button(frame_jours, text="+ Ajouter un jour", command=ajouter_jour_ferie).grid(row=99, column=0, pady=5)

    # Résumé des jours chômés
    frame_resume = tk.LabelFrame(cadre, text="Résumé des jours chômés")
    frame_resume.pack(fill="both", expand=True, padx=10, pady=5)
    text_resume = tk.Text(frame_resume, height=6, state="disabled")
    text_resume.pack(fill="both", expand=True)

    def maj_resume_jours_feries(calendrier):
        try:
            def est_pendant_vacances(jour):
                for (debut, reprise) in calendrier.vacances.values():
                    if debut <= jour < reprise:
                        return True
                return False

            visibles = [j for j in calendrier.jours_feries if not est_pendant_vacances(j)]
            visibles = sorted(set(visibles))

            text_resume.configure(state="normal")
            text_resume.delete("1.0", tk.END)
            for j in visibles:
                text_resume.insert(tk.END, j.strftime("%Y-%m-%d") + "\n")
            text_resume.configure(state="disabled")
        except:
            pass

    def valider():
        try:
            rentree_date = date.fromisoformat(entry_rentree.get())
            fin_date = date.fromisoformat(entry_fin.get())
            if fin_date <= rentree_date:
                messagebox.showerror("Erreur", "La date de fin doit être après la rentrée.")
                return

            vacances = {}
            for nom, (e_debut, e_reprise) in vacances_entries.items():
                debut = date.fromisoformat(e_debut.get().strip())
                reprise = date.fromisoformat(e_reprise.get().strip())
                vacances[nom] = (debut, reprise)

            jours_manuels = []
            for widgets in jours_feries_widgets:
                entry = widgets[0]
                try:
                    j = date.fromisoformat(entry.get().strip())
                    jours_manuels.append(j)
                except:
                    continue

            cal = Calendrier(rentree=rentree_date, fin=fin_date, vacances=vacances, jours_feries_manuel=jours_manuels)
            app.db['calendrier'] = cal
            construire_arborescence_gauche(treeview, app)
            maj_resume_jours_feries(cal)
            messagebox.showinfo("Succès", "Calendrier enregistré.")

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur lors de la validation : {e}")

    tk.Button(cadre, text="Valider le calendrier", command=valider).pack(pady=10)

    if cal:
        maj_resume_jours_feries(cal)

def afficher_formulaire_edition_classe(app, inner_haut, classe_id,treeview):
    # Nettoyage du cadre
    for widget in inner_haut.winfo_children():
        widget.destroy()
    app.help_text = "Vous pouvez ici éditer les informations de la classe. \n"
    mettre_a_jour_aide(app)

    classe = app.db["classes"][classe_id]

    row = 0

    # === Nom de la classe ===
    tk.Label(inner_haut, text="Nom de la classe :").grid(row=row, column=0, sticky="w", padx=10, pady=5)
    entry_nom = tk.Entry(inner_haut)
    entry_nom.insert(0, classe.nom)
    entry_nom.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
    row += 1

    # === Options ===
    tk.Label(inner_haut, text="Options de la classe :").grid(row=row, column=0, sticky="w", padx=10, pady=5)
    frame_options = tk.Frame(inner_haut)
    frame_options.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
    row += 1

    # Liste des options
    options_vars = {}
    def afficher_options():
        for widget in frame_options.winfo_children():
            widget.destroy()

        for opt in list(options_vars.keys()):
            var = options_vars[opt]
            frame = tk.Frame(frame_options)
            frame.grid(sticky="w")
            tk.Label(frame, text=opt).grid(row=0, column=0, sticky="w")
            if opt!=classe.nom:
                btn_suppr = tk.Button(frame, text="❌", command=lambda o=opt: supprimer_option(o))
                btn_suppr.grid(row=0, column=1, padx=5)

    def ajouter_option():
        nouvelle = entry_ajout_option.get().strip()
        if nouvelle and nouvelle not in options_vars:
            options_vars[nouvelle] = tk.BooleanVar(value=True)
            afficher_options()
            entry_ajout_option.delete(0, tk.END)

    def supprimer_option(opt):
        if opt in options_vars:
            del options_vars[opt]
            afficher_options()

    # Initialisation des options existantes
    for opt in classe.options:
        options_vars[opt] = tk.BooleanVar(value=True)

    afficher_options()

    # Ajout d'une nouvelle option
    entry_ajout_option = tk.Entry(inner_haut)
    entry_ajout_option.grid(row=row, column=0, padx=10, pady=5, sticky="ew")
    btn_ajout_option = tk.Button(inner_haut, text="Ajouter option", command=ajouter_option)
    btn_ajout_option.grid(row=row, column=1, padx=10, pady=5, sticky="w")
    row += 1

    # === Semaines de colles ===
    tk.Label(inner_haut, text="Semaines de colles :").grid(row=row, column=0, columnspan=2,sticky="w", padx=10, pady=5)
    row+=1
    frame_semaines = tk.Frame(inner_haut)
    frame_semaines.grid(row=row, column=0, columnspan=2,sticky="w", padx=10, pady=5)
    row += 1

    semaines_possibles = app.db['calendrier'].get_all_semaines()
    semaines_vars = {}

    col_count = 3
    col = 0
    lig = 0

    for i, (num_semaine, (debut, fin)) in enumerate(semaines_possibles.items()):
        var = tk.IntVar(value=1 if num_semaine in classe.semaines_colles else 0)
        cb = tk.Checkbutton(frame_semaines, text=f"Semaine {num_semaine} du {debut.strftime('%d/%m')} au {fin.strftime('%d/%m')}", variable=var)
        cb.grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=2)
        semaines_vars[num_semaine]=var
        col += 1
        if col >= col_count:
            col = 0
            lig += 1

    def tout_cocher():
        for i,var in semaines_vars.items():
            var.set(True)

    def tout_decocher():
        for i,var in semaines_vars.items():
            var.set(False)

    btn_tout_cocher = tk.Button(inner_haut, text="Tout cocher", command=tout_cocher)
    btn_tout_cocher.grid(row=row, column=0, padx=10, pady=5)
    btn_tout_decocher = tk.Button(inner_haut, text="Tout décocher", command=tout_decocher)
    btn_tout_decocher.grid(row=row, column=1, padx=10, pady=5)
    row += 1

    # === Nombre de colles max / semaine ===
    tk.Label(inner_haut, text="Nb de colles max par semaine :").grid(row=row, column=0, sticky="w", padx=10, pady=5)
    entry_nb_colles = tk.Entry(inner_haut)
    entry_nb_colles.insert(0, str(classe.nbCollesMax or ""))
    entry_nb_colles.grid(row=row, column=1, sticky="ew", padx=10, pady=5)
    row += 1

    # === Boutons ===
    def modifier():
        nouveau_nom = entry_nom.get().strip()
        if not nouveau_nom:
            messagebox.showerror("Erreur", "Le nom de la classe ne peut pas être vide.")
            return

        try:
            nb_colles = int(entry_nb_colles.get())
        except ValueError:
            messagebox.showerror("Erreur", "Le nombre de colles maximum doit être un entier.")
            return

        nouvelles_options = list(options_vars.keys())

        # Semaines de colles cochées
        semaines_colles = [
            i for i, var in semaines_vars.items() if var.get() == 1
        ]

        # Mise à jour de la classe dans app.db
        classe.nom = nouveau_nom
        classe.options = nouvelles_options
        classe.nbCollesMax = nb_colles
        classe.semaines_colles = semaines_colles
        classe.semaines_cours=sorted(semaines_possibles.keys())

        # Confirmation
        messagebox.showinfo("Succès", f"Les informations de la classe '{classe.nom}' ont été mises à jour.")

        # Mise à jour de l’arborescence
        construire_arborescence_gauche(treeview, app)

    def supprimer():
        if not messagebox.askyesno("Confirmation", f"Supprimer la classe {classe.nom} et toutes ses données associées ?"):
            return

        # Supprimer matières de cette classe
        matieres_a_supprimer = [mid for mid, m in app.db["matieres"].items() if m.classe.id == classe.id]
        for mid in matieres_a_supprimer:
            mat= app.db["matieres"][mid]
            # Nettoyer les colleurs et les horaires de la matière
            colleurs_a_supprimer=[]
            for col in mat.colleurs:
                col.matieres.remove(mat)
                if col.matieres==[]:
                    for h in col.horaires:
                        del app.db["horaires"][h.id]
                    colleurs_a_supprimer.append(col)
                else:
                    for h in col.horaires:
                        h.matieres.remove(mat)
                        if h.matieres==[]:
                            del app.db["horaires"][h.id]
            for col in colleurs_a_supprimer:
                del app.db['colleurs'][col.id]

            del app.db["matieres"][mid]

        # Supprimer TP
        app.db["TP"] = {k: v for k, v in app.db["TP"].items() if v.classe.id != classe.id}

        # Supprimer étudiants
        app.db["etudiants"] = {k: v for k, v in app.db["etudiants"].items() if v.classe.id != classe.id}

        # Supprimer EDT de la classe
        for opt,h in classe.edt.items():
            del app.db['horaires'][h.id]

        # Supprimer la classe
        del app.db["classes"][classe.id]



        app.help_text = f"Classe « {classe.nom} » et ses données associées ont été supprimées."
        messagebox.showinfo("Suppression", f"Classe {classe.nom} supprimée.")
        app.aide_widget.config(state="normal")
        app.aide_widget.delete("1.0", tk.END)
        app.aide_widget.insert("1.0", app.help_text)
        app.aide_widget.config(state="disabled")

        construire_arborescence_gauche(app.treeview, app)

    tk.Button(inner_haut, text="Modifier les informations de la classe", command=modifier).grid(row=row,column=0,pady=(10, 5))
    tk.Button(inner_haut, text="Supprimer la classe", command=supprimer).grid(row=row,column=1,pady=(0, 10))

def afficher_formulaire_creation_groupe_matiere(app, frame, treeview, classe_id):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Vous pouvez créer ici des groupements de matières afin d'imposer l'alternance  des colles des matières groupées pour les étudiants. \n Vous devez d'abord choisir une option (l'option par défaut avec le nom de la classe s'appliquera à tous les étudiants), puis les matières (à alternance fixe) qui composeront le groupement et en enfin vous choisissez des décalages afin d'obtenir l'alternance souhaitée.\n Attention au choix des options et des matières, un étudiant ne doit pas être concerné par deux groupements qui intègrent la même matière.\n Vous n'êtes pas obligé de grouper chaque matière à alternance fixe, vous pouvez laisser le programme décider de l'alternance si vous le souhaitez."
    mettre_a_jour_aide(app)

    classe = app.db["classes"][classe_id]

    # Titre
    tk.Label(frame, text="Création d’un groupement de matières/TP", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=3, pady=10)

    # Choix de l’option
    tk.Label(frame, text="Choisir une option :").grid(row=1, column=0, sticky="w", padx=5)
    option_var = tk.StringVar()
    option_menu = ttk.Combobox(frame, textvariable=option_var, values=classe.options, state="readonly")
    option_menu.grid(row=1, column=1, sticky="w", padx=5)

    # Zone de sélection des matières/TP
    frame_matiere = tk.LabelFrame(frame, text="Sélectionner les matières ou TP")
    frame_matiere.grid(row=2, column=0, columnspan=3, padx=5, pady=10, sticky="nsew")
    frame.grid_rowconfigure(2, weight=1)

    # Aperçu
    frame_apercu = tk.LabelFrame(frame, text="Aperçu des périodes (répétées jusqu’au PPCM)")
    frame_apercu.grid(row=3, column=0, columnspan=3, padx=5, pady=10, sticky="nsew")
    frame.grid_rowconfigure(3, weight=1)

    apercu_labels = []

    var_matiere_dict = {}

    def update_apercu(*args):
        for w in apercu_labels:
            w.destroy()
        apercu_labels.clear()

        selected = [m for m in var_matiere_dict if var_matiere_dict[m][0].get()]

        periodes = []

        for m in selected:
            opt = option_var.get()
            periode = m.periodes.get(opt, "")
            periodes.append(len(periode))

        if not periodes:
            return

        longueur_finale = ppcm_liste(periodes)

        for i, m in enumerate(selected):
            opt = option_var.get()
            periode = m.periodes.get(opt, "")
            dec = int(var_matiere_dict[m][1].get())

            etendue_complete = (periode * ((longueur_finale // len(periode)) + 2))[:longueur_finale]
            # Décalage circulaire à gauche
            etendue = etendue_complete[dec:] + etendue_complete[:dec]

            # Ligne : nom de la matière
            ligne_frame = tk.Frame(frame_apercu)
            ligne_frame.grid(row=i, column=0, columnspan=2, sticky="w", padx=10, pady=2)

            label_nom = tk.Label(ligne_frame, text=f"{m.nom:<15}", width=15, anchor="w")
            label_nom.pack(side="left", padx=(0, 5))
            apercu_labels.append(label_nom)

            # Ligne : 0/1 colorés
            for c in etendue:
                couleur = "green" if c == "1" else "lightgrey"
                case = tk.Label(ligne_frame, text=c, bg=couleur, width=2, borderwidth=1, relief="solid")
                case.pack(side="left", padx=1)
                apercu_labels.append(case)


    def update_matiere_selection(*args):
        for widget in frame_matiere.winfo_children():
            widget.destroy()
        var_matiere_dict.clear()

        option = option_var.get()
        candidats = []

        for m in app.db.get("matieres", {}).values():
            if m.classe.id == classe_id and option in m.options and m.alternance_fixe:
                candidats.append(m)
        for tp in app.db.get("TPs", {}).values():
            if tp.classe.id == classe_id and option in tp.options and tp.alternance_fixe:
                candidats.append(tp)

        if not candidats:
            tk.Label(frame_matiere, text="Aucune matière/TP disponible pour cette option").grid(row=0, column=0, padx=5, pady=5)
            return

        for i, obj in enumerate(candidats):
            var_check = tk.BooleanVar()
            chk = tk.Checkbutton(frame_matiere, text=obj.nom, variable=var_check, command=update_apercu)
            chk.grid(row=i, column=0, sticky="w", padx=5)

            periode = obj.periodes.get(option, "")
            longueur = len(periode)

            var_spin = tk.IntVar(value=0)
            spin = tk.Spinbox(frame_matiere, from_=0, to=longueur-1, width=5, textvariable=var_spin)
            spin.grid(row=i, column=1, sticky="w", padx=5)

            var_spin.trace_add("write", lambda *a: update_apercu())
            var_matiere_dict[obj] = (var_check, var_spin)

        update_apercu()

    option_var.trace_add("write", lambda *args: update_matiere_selection())

    # Bouton de validation
    def valider():
        opt = option_var.get()
        if not opt:
            tk.messagebox.showerror("Erreur", "Vous devez sélectionner une option.")
            return

        selected = [(m, int(var.get())) for m, (check, var) in var_matiere_dict.items() if check.get()]
        if len(selected) < 2:
            tk.messagebox.showerror("Erreur", "Vous devez sélectionner au moins deux matières ou TP.")
            return

        cle = (tuple(m for m, _ in selected), opt)
        decalages = [d for _, d in selected]
        app.db["classes"][classe_id].matieres_groupees[cle] = decalages

        tk.messagebox.showinfo("Succès", "Groupement ajouté avec succès.")
        construire_arborescence_gauche(treeview, app)

    btn_valider = tk.Button(frame, text="Créer le groupe de matières", command=valider)
    btn_valider.grid(row=4, column=0, columnspan=2, pady=10)

def afficher_formulaire_modification_groupe_matiere(app, inner_haut, treeview, classe_id, groupe_iid):
    for widget in inner_haut.winfo_children():
        widget.destroy()

    app.help_text = "Vous ne pouvez que supprimer le groupement ici, si vous souhaitez modifier il faura en recréer un nouveau."
    mettre_a_jour_aide(app)
    # Extraire les IDs
    parts = groupe_iid.split("_grp_")[1].rsplit("_", 1)
    mat_ids = parts[0].split("_")
    option = parts[1]

    classe = app.db['classes'][classe_id]
    key = tuple((m for m in app.db['matieres'].values() if m.id in mat_ids)), option
    decalages = classe.matieres_groupees.get(key, [])

    # Récupération des objets matière dans le bon ordre
    matieres = [m for m in app.db['matieres'].values() if m.id in mat_ids]
    matieres.sort(key=lambda m: mat_ids.index(m.id))  # Respecter l’ordre de mat_ids

    # Récupération de la période pour chaque matière
    periodes = []
    longueurs = []

    for m in matieres:
        p = m.periodes.get(option, "")
        periodes.append(p)
        longueurs.append(len(p))

    # Calcul du PPCM des longueurs
    longueur_finale = ppcm_liste(longueurs)

    # Titre
    tk.Label(inner_haut, text="Visualisation de l'alternance :", font=("Arial", 12, "bold")).grid(row=2, column=0, columnspan=2, pady=(10, 0))

    # Affichage avec couleur
    for idx, (m, p, decalage) in enumerate(zip(matieres, periodes, decalages)):
        # Allonger et décaler la période
        periode_etendue = (p * (longueur_finale // len(p) + 1))[:longueur_finale]
        decalee = periode_etendue[decalage:] + periode_etendue[:decalage]

        # Créer un frame ligne avec nom et 0/1 colorés
        ligne_frame = tk.Frame(inner_haut)
        ligne_frame.grid(row=3 + idx, column=0, columnspan=2, sticky="w", padx=10, pady=2)

        tk.Label(ligne_frame, text=f"{m.nom:<15}", width=15, anchor="w").pack(side="left")

        for c in decalee:
            couleur = "green" if c == "1" else "lightgrey"
            case = tk.Label(ligne_frame, text=c, bg=couleur, width=2, borderwidth=1, relief="solid")
            case.pack(side="left", padx=1)


    btn_supprimer = tk.Button(inner_haut, text="Supprimer ce groupement", fg="white", bg="red")

    btn_supprimer.grid(row= 1, column=0, columnspan=2, pady=10)

    def supprimer_groupement():
        reponse = messagebox.askyesno("Confirmation", "Voulez-vous vraiment supprimer ce groupement ?")
        if not reponse:
            return

        try:
            del classe.matieres_groupees[key]


            # Supprimer du treeview
            if treeview.exists(groupe_iid):
                treeview.delete(groupe_iid)

            messagebox.showinfo("Succès", "Groupement supprimé.")
            # Réinitialiser le cadre droit
            for widget in inner_haut.winfo_children():
                widget.destroy()
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de supprimer le groupement.\n{e}")

    btn_supprimer.config(command=supprimer_groupement)

def afficher_formulaire_ajout_matiere(app, frame, treeview, classe_id):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Vous pouvez ici ajouter une matière à la classe. N'ajoutez que des matières qui sont concernées par des colles.\n Vous devez ensuite définir une période de colles pour la matière avec une chaîne de 0 et de 1 (1 correspondant à une semaine avec colle de cette matière, 0 à une semaine sans colle de cette matière. Les périodes peuvent être différentes selon les options, vous devez donc choisir une option au préalable. (l'option avec le nom de la classe signifie que la période d'applique à tous les étudiants). Attention au choix des options, un étudiant ne doit pas être concerné par plusieurs périodes de la même matière !\n Quelques exemples : Pour une colle toutes les semaines, la période est '1', pour une colle toute les deux semaines, la période est '10' (ou '01' cela n'a pas d'importance). Pour les colles de français en première année (3 par an), considérez qu'il y a une colle toutes les 10 semaines, la période est donc '1000000000'.\n Le nombre de colles max par an est dans la plupart des cas à laisser tel quel, il concerne par exemple les colles de français en deuxième année (2 colles dans l'année, 1 colle toutes les 10 semaines, 25 semaines de colles par an) où un étudiant qui a eu colle la première semaine ne devrait pas avoir une troisème colle la 21ème semaine.\n La durée de la colle correspond à la durée totale en minutes pour un étudiant (préparation +passage), la durée de préparation n'a pas d'incidence pour la résolution, seulement pour la mise en forme.\n Le paramètre 'colle par groupe permet de choisir si les colles de cette matière doivent concerner tous les étudiants d'un même groupe de colle ou si les colles peuvent être individualisées ou si les étudiants de groupes différents peuvent être mélangés. Attention à garder ce paramètre cohérent avec le nombre de places disponibles (si vous individualisez avec une place dispo, il ne faut pas avoir 'oui' pour 'colle par groupe').\n Le paramètre 'alternance fixe' permet de décider si cette matière fera partie du groupe de matières dont l'alternance avec les autres sera la même pour tous les étudiants. Si le paramètre est fixé à 'non', cela permet plus de souplesse dans la gestion des horaires de colles de cette matière (conseillé pour le français, en particulier si vous l'individualisez) "
    mettre_a_jour_aide(app)

    classe = app.db['classes'][classe_id]
    row = 0

    tk.Label(frame, text="Nom de la matière :").grid(row=row, column=0, sticky="w")
    entry_nom = tk.Entry(frame)
    entry_nom.grid(row=row, column=1, sticky="w")
    row += 1

    # =====================
    # Périodes
    # =====================
    tk.Label(frame, text="Option :").grid(row=row, column=0, sticky="w")
    option_var = tk.StringVar()
    option_menu = ttk.Combobox(frame, textvariable=option_var, values=classe.options, state="readonly")
    option_menu.grid(row=row, column=1, sticky="w")
    row += 1

    tk.Label(frame, text="Période (suite de 0 et 1) :").grid(row=row, column=0, sticky="w")
    entry_periode = tk.Entry(frame)
    entry_periode.grid(row=row, column=1, sticky="w")
    row += 1

    periodes = {}
    periode_listbox = tk.Listbox(frame, height=5)

    def valider_periode():
        opt = option_var.get()
        per = entry_periode.get().strip()
        if not opt or any(c not in "01" for c in per):
            messagebox.showerror("Erreur", "Option invalide ou période mal formée.")
            return
        periodes[opt] = per
        periode_listbox.insert(tk.END, f"{opt} : {per}")
        entry_periode.delete(0, tk.END)

    btn_valider_periode = tk.Button(frame, text="Valider la période", command=valider_periode)
    btn_valider_periode.grid(row=row, column=2, sticky="w")
    row += 1

    periode_listbox.grid(row=row, column=0, columnspan=3, sticky="we")
    row += 1

    # =====================
    # Paramètres des colles
    # =====================
    def champ_avec_label(label, default, row):
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
        e = tk.Entry(frame)
        e.insert(0, str(default))
        e.grid(row=row, column=1, sticky="w")
        return e

    entry_colles_max = champ_avec_label("Nb colles max/an :", 30, row); row += 1
    entry_duree_colle = champ_avec_label("Durée colle (min) :", 55, row); row += 1
    entry_preparation = champ_avec_label("Durée préparation (min) :", 0, row); row += 1
    entry_decalage=champ_avec_label("Décalage du début des colles (en semaines) :",0,row);row+=1

    tk.Label(frame, text="Colle par groupe :").grid(row=row, column=0, sticky="w")
    groupes_var = tk.StringVar(value="Oui")
    ttk.Combobox(frame, textvariable=groupes_var, values=["Oui", "Non"], state="readonly").grid(row=row, column=1, sticky="w")
    row += 1

    entry_places = champ_avec_label("Places disponibles :", 3, row); row += 1

    tk.Label(frame, text="Alternance fixe :").grid(row=row, column=0, sticky="w")
    alternance_var = tk.StringVar(value="Oui")
    ttk.Combobox(frame, textvariable=alternance_var, values=["Oui", "Non"], state="readonly").grid(row=row, column=1, sticky="w")
    row += 1


    def ajouter():
        nom = entry_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Nom requis")
            return
        if not periodes:
            messagebox.showerror("Erreur", "Ajoutez au moins une période")
            return

        try:
            nbMax = int(entry_colles_max.get())
            duree = int(entry_duree_colle.get())
            prep = int(entry_preparation.get())
            places = int(entry_places.get())
            decalage=int(entry_decalage.get())
        except ValueError:
            messagebox.showerror("Erreur", "Les champs numériques sont invalides.")
            return

        m_id = str(app.id)
        app.id += 1
        nouvelle = matiere(
            id=m_id,
            nom=nom,
            classe=classe,
            periodes=periodes.copy(),
            nbCollesMax=nbMax,
            dureeColle=duree,
            dureePreparation=prep,
            groupes_fixes=(groupes_var.get() == "Oui"),
            colleurs=[],
            places=places,
            alternance_fixe=(alternance_var.get() == "Oui"),
            decalage_semaines=decalage
        )
        app.db['matieres'][m_id] = nouvelle
        classe.matieres.append(nouvelle)
        messagebox.showinfo("Succès", "Matière ajoutée.")
        afficher_formulaire_ajout_matiere(app, frame, treeview, classe_id)  # Reset
        construire_arborescence_gauche(treeview,app)

    tk.Button(frame, text="Ajouter la matière", command=ajouter).grid(row=row, column=0, columnspan=2, pady=10)

def afficher_formulaire_edition_matiere(app, frame, treeview, classe_id, matiere_id):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Vous pouvez ici modifier ou supprimer la matière."
    mettre_a_jour_aide(app)

    classe = app.db['classes'][classe_id]
    matiere = app.db['matieres'][matiere_id]

    tk.Label(frame, text="Nom de la matière :").grid(row=0, column=0, sticky="w")
    entry_nom = tk.Entry(frame)
    entry_nom.insert(0, matiere.nom)
    entry_nom.grid(row=0, column=1, sticky="w")

    row = 1
    periodes = matiere.periodes.copy()
    periode_entries = {}

    tk.Label(frame, text="Périodes par option :").grid(row=row, column=0, sticky="w")
    row += 1
    for opt in classe.options:
        tk.Label(frame, text=f"Option : {opt}").grid(row=row, column=0, sticky="w")
        entry = tk.Entry(frame)
        entry.insert(0, periodes.get(opt, ""))
        entry.grid(row=row, column=1, sticky="w")
        periode_entries[opt] = entry
        row += 1

    # Champs numériques
    def champ_num(label, valeur, r):
        tk.Label(frame, text=label).grid(row=r, column=0, sticky="w")
        entry = tk.Entry(frame)
        entry.insert(0, str(valeur))
        entry.grid(row=r, column=1, sticky="w")
        return entry

    entry_colles_max = champ_num("Nombre de colles max dans l'année", matiere.nbCollesMax, row)
    row += 1
    entry_duree_colle = champ_num("Durée de la colle (min)", matiere.dureeColle, row)
    row += 1
    entry_prepa = champ_num("Durée de la préparation (min)", matiere.dureePreparation, row)
    row += 1
    entry_places = champ_num("Places disponibles pour une colle", matiere.places, row)
    row += 1
    entry_decalage=champ_num("Décalage du début des colles (en semaines) :",matiere.decalage_semaines,row)
    row+=1

    # Choix booléens
    def champ_choix(label, valeur, r):
        tk.Label(frame, text=label).grid(row=r, column=0, sticky="w")
        var = tk.StringVar(value="Oui" if valeur else "Non")
        choix = ttk.Combobox(frame, textvariable=var, values=["Oui", "Non"], state="readonly")
        choix.grid(row=r, column=1, sticky="w")
        return var

    var_groupes = champ_choix("Colle par groupe ?", matiere.groupes_fixes, row)
    row += 1
    var_alternance = champ_choix("Matière à alternance fixe ?", matiere.alternance_fixe, row)
    row += 1

    def modifier():
        nom = entry_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Le nom est obligatoire.")
            return

        new_periodes = {}
        for opt, entry in periode_entries.items():
            p = entry.get().strip()
            if p:
                new_periodes[opt] = p

        try:
            matiere.nom = nom
            matiere.periodes = new_periodes
            matiere.options = list(new_periodes.keys())
            matiere.nbCollesMax = int(entry_colles_max.get())
            matiere.dureeColle = int(entry_duree_colle.get())
            matiere.dureePreparation = int(entry_prepa.get())
            matiere.places = int(entry_places.get())
            matiere.groupes_fixes = var_groupes.get() == "Oui"
            matiere.alternance_fixe = var_alternance.get() == "Oui"
            matiere.decalage_semaines=int(entry_decalage.get())

            messagebox.showinfo("Succès", "Matière modifiée.")
        except Exception as e:
            messagebox.showerror("Erreur", f"Impossible de modifier la matière : {e}")

    def supprimer():
        if messagebox.askyesno("Confirmation", "Supprimer cette matière ?"):
            try:
                colleurs_a_supprimer=[]
                for col in matiere.colleurs:
                    col.matieres.remove(matiere)
                    if col.matieres==[]:
                        colleurs_a_supprimer.append(col)
                        for h in col.horaires:
                            del app.db['horaires'][h.id]
                    else:
                        for h in col.horaires:
                            h.matieres.remove(matiere)
                            if h.matieres==[]:
                                del app.db['horaires'][h.id]
                for col in colleurs_a_supprimer:
                    del app.db['colleurs'][col.id]
                del app.db['matieres'][matiere.id]

                messagebox.showinfo("Succès", "Matière supprimée.")
                construire_arborescence_gauche(treeview,app)
                for widget in frame.winfo_children():
                    widget.destroy()
            except Exception as e:
                messagebox.showerror("Erreur", f"Impossible de supprimer la matière : {e}")

    btn_modifier = tk.Button(frame, text="Modifier", command=modifier)
    btn_modifier.grid(row=row, column=0, pady=10)
    btn_supprimer = tk.Button(frame, text="Supprimer", fg="white", bg="red", command=supprimer)
    btn_supprimer.grid(row=row, column=1, pady=10)



def afficher_formulaire_creation_colleur(app, frame, treeview, matiere_id):
    _formulaire_colleur(app, frame, treeview, matiere_id, col=None)

def afficher_formulaire_edition_colleur(app, frame, treeview, matiere_id, colleur_id):
    col = app.db['colleurs'][colleur_id]
    _formulaire_colleur(app, frame, treeview, matiere_id, col=col)

def _formulaire_colleur(app, frame, treeview, matiere_id, col=None):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Les colleurs peuvent être affectés à différentes matières (peu probable) mais surout à différentes classes si vous gérez plusieurs classes en même temps. Vous devez choisir au moins une classe et une matière et remplir le nombre d'heures que le colleur donne dans cette matière, qui peut être un nombre non entier (attention, le séprateur pour la partie décimale est un point et pas une virgule). Par exemple, un colleur qui donne une colle toutes les deux semaines aura un nombre d'heures égal à 0.5. Ne vous préoccupez pas trop des arrondis si vos fractions n'ont pas d'écriture décimale, l'important est surtout d'avoir une borne inf et une borne sup entières."
    mettre_a_jour_aide(app)

    matiere = app.db['matieres'][matiere_id]
    classe_matiere = matiere.classe

    is_edit = col is not None
    horaires_placeholder = []  # À gérer plus tard si besoin

    row = 0
    tk.Label(frame, text="Nom du colleur :").grid(row=row, column=0, sticky="w")
    entry_nom = tk.Entry(frame)
    entry_nom.grid(row=row, column=1, sticky="w")
    if is_edit:
        entry_nom.insert(0, col.nom)
    row += 1

    tk.Label(frame, text="Matières affectées :").grid(row=row, column=0, sticky="w", pady=(10, 0))
    row += 1

    matiere_heures = {}
    listebox_matieres = tk.Listbox(frame, height=5, width=50)
    listebox_matieres.grid(row=row, column=0, columnspan=3, sticky="w")
    row += 1

    def rafraichir_listebox():
        listebox_matieres.delete(0, tk.END)
        for m, h in matiere_heures.items():
            listebox_matieres.insert(tk.END, f"{m.nom} ({m.classe.nom}) : {h} h")

    # Si édition, on pré-remplit
    if is_edit:
        for m in col.matieres:
            h = col.heures.get(m, 0.0)
            matiere_heures[m] = h


    rafraichir_listebox()

    def supprimer_matiere():
        selection = listebox_matieres.curselection()
        if not selection:
            return
        idx = selection[0]
        mat = list(matiere_heures.keys())[idx]
        del matiere_heures[mat]
        rafraichir_listebox()

    btn_supprimer = tk.Button(frame, text="Supprimer la matière sélectionnée", command=supprimer_matiere)
    btn_supprimer.grid(row=row, column=0, columnspan=2, pady=5)
    row += 1

    tk.Label(frame, text="Ajouter matière :").grid(row=row, column=0, sticky="w", pady=(10, 0))
    row += 1

    classes_dispo = list(app.db['classes'].values())
    classe_var = tk.StringVar()
    matiere_var = tk.StringVar()
    heures_var = tk.StringVar()

    combo_classe = ttk.Combobox(frame, textvariable=classe_var, values=[c.nom for c in classes_dispo], state="readonly")
    combo_classe.grid(row=row, column=0, sticky="w")
    combo_matiere = ttk.Combobox(frame, textvariable=matiere_var, state="readonly")
    combo_matiere.grid(row=row, column=1, sticky="w")
    row += 1

    def update_matieres_disponibles(event=None):
        cls = next((c for c in classes_dispo if c.nom == classe_var.get()), None)
        if cls:
            combo_matiere['values'] = [m.nom for m in cls.matieres]

    combo_classe.bind("<<ComboboxSelected>>", update_matieres_disponibles)

    tk.Label(frame, text="Heures :").grid(row=row, column=0, sticky="w")
    entry_heures = tk.Entry(frame, textvariable=heures_var)
    entry_heures.grid(row=row, column=1, sticky="w")
    row += 1

    def ajouter_matiere():
        cls = next((c for c in classes_dispo if c.nom == classe_var.get()), None)
        if not cls:
            messagebox.showerror("Erreur", "Classe invalide")
            return
        mat = next((m for m in cls.matieres if m.nom == matiere_var.get()), None)
        if not mat:
            messagebox.showerror("Erreur", "Matière invalide")
            return
        try:
            h = float(heures_var.get().replace(",", "."))
        except ValueError:
            messagebox.showerror("Erreur", "Heures invalides")
            return
        if mat in matiere_heures:
            messagebox.showwarning("Doublon", "Cette matière est déjà assignée")
            return
        matiere_heures[mat] = h
        heures_var.set("")
        rafraichir_listebox()

    tk.Button(frame, text="Ajouter", command=ajouter_matiere).grid(row=row, column=0, columnspan=2, pady=5)
    row += 1

    def valider_ou_modifier():
        nom = entry_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Nom requis")
            return
        if not matiere_heures:
            messagebox.showerror("Erreur", "Aucune matière assignée")
            return

        if is_edit:
            col.nom = nom
            col.heures = matiere_heures.copy()
            col.matieres = list(matiere_heures.keys())
        else:
            c_id = str(app.id)
            app.id += 1
            nouveau_colleur = app.db['colleurs'].get(c_id)
            if not nouveau_colleur:
                nouveau_colleur = colleur(id=c_id, nom=nom, horaires=horaires_placeholder, heures=matiere_heures.copy())
                nouveau_colleur.matieres = list(matiere_heures.keys())
                app.db['colleurs'][c_id] = nouveau_colleur
                for m in matiere_heures:
                    m.colleurs.append(nouveau_colleur)
        # Mettre à jour la présence du colleur dans les matières
        # Réinitialiser la présence du colleur dans toutes les matières
        for mat in app.db['matieres'].values():
            if is_edit and col in mat.colleurs:
                mat.colleurs.remove(col)
            if not is_edit:
                if nouveau_colleur in mat.colleurs:
                    mat.colleurs.remove(nouveau_colleur)

        # Réaffecter le colleur uniquement aux bonnes matières
        for m in matiere_heures:
            if is_edit:
                m.colleurs.append(col)
            else:
                m.colleurs.append(nouveau_colleur)

        #Modifier les horaires en cas de suppression de matiere :
        if is_edit:
            for h in col.horaires:
                mat_to_remove=[]
                for mat in h.matieres:
                    if mat not in col.matieres:
                        mat_to_remove.append(mat)
                for mat in mat_to_remove:
                    h.matieres.remove(mat)



        construire_arborescence_gauche(treeview, app)
        messagebox.showinfo("Succès", "Colleur enregistré.")

    def supprimer_colleur():
        if not is_edit:
            return
        confirm = messagebox.askyesno("Confirmation", "Supprimer ce colleur ?")
        if confirm:
            for m in col.matieres:
                if col in m.colleurs:
                    m.colleurs.remove(col)
            for h in col.horaires:
                del app.db['horaires'][h.id]
            del app.db['colleurs'][col.id]

            messagebox.showinfo("Supprimé", "Colleur supprimé.")
            for widget in frame.winfo_children():
                widget.destroy()
            construire_arborescence_gauche(treeview, app)

    if is_edit:
        tk.Button(frame, text="Modifier", command=valider_ou_modifier).grid(row=row, column=0, pady=10)
        tk.Button(frame, text="Supprimer", command=supprimer_colleur).grid(row=row, column=1, pady=10)
    else:
        tk.Button(frame, text="Valider", command=valider_ou_modifier).grid(row=row, column=0, columnspan=2, pady=10)




def afficher_formulaire_creation_tp(app, frame, treeview, classe_id):
    _formulaire_tp(app, frame, treeview, classe_id, tp=None)

def afficher_formulaire_edition_tp(app, frame, treeview, classe_id, tp_id):
    tp = app.db['TPs'][tp_id]
    _formulaire_tp(app, frame, treeview, classe_id, tp=tp)

def _formulaire_tp(app, frame, treeview, classe_id, tp=None):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Les TP/TD permettent de défnir des groupes dynamiques selon les contraintes de colles. Voir l'aide sur les matières pour les explications sur les différents champs."
    mettre_a_jour_aide(app)

    classe = app.db['classes'][classe_id]
    is_edit = tp is not None

    row = 0
    tk.Label(frame, text="Nom du TP/TD :").grid(row=row, column=0, sticky="w")
    entry_nom = tk.Entry(frame)
    if is_edit:
        entry_nom.insert(0, tp.nom)
    entry_nom.grid(row=row, column=1, sticky="w")
    row += 1

    # =====================
    # Périodes
    # =====================
    tk.Label(frame, text="Option :").grid(row=row, column=0, sticky="w")
    option_var = tk.StringVar()
    option_menu = ttk.Combobox(frame, textvariable=option_var, values=classe.options, state="readonly")
    option_menu.grid(row=row, column=1, sticky="w")
    row += 1

    tk.Label(frame, text="Période (suite de 0 et 1) :").grid(row=row, column=0, sticky="w")
    entry_periode = tk.Entry(frame)
    entry_periode.grid(row=row, column=1, sticky="w")
    row += 1

    periodes = {} if not is_edit else dict(tp.periodes)
    periode_listbox = tk.Listbox(frame, height=5)

    def valider_periode():
        opt = option_var.get()
        per = entry_periode.get().strip()
        if not opt or any(c not in "01" for c in per):
            messagebox.showerror("Erreur", "Option invalide ou période mal formée.")
            return
        periodes[opt] = per
        rafraichir_periodes()
        entry_periode.delete(0, tk.END)

    def rafraichir_periodes():
        periode_listbox.delete(0, tk.END)
        for opt, per in periodes.items():
            periode_listbox.insert(tk.END, f"{opt} : {per}")

    btn_valider_periode = tk.Button(frame, text="Valider la période", command=valider_periode)
    btn_valider_periode.grid(row=row, column=2, sticky="w")
    row += 1

    rafraichir_periodes()
    periode_listbox.grid(row=row, column=0, columnspan=3, sticky="we")
    row += 1

    def champ_avec_label(label, default, row, current=None):
        tk.Label(frame, text=label).grid(row=row, column=0, sticky="w")
        e = tk.Entry(frame)
        e.insert(0, str(current if current is not None else default))
        e.grid(row=row, column=1, sticky="w")
        return e

    # Groupes fixes
    tk.Label(frame, text="TP/TD par groupe :").grid(row=row, column=0, sticky="w")
    groupes_var = tk.StringVar(value="Oui" if not is_edit or tp.groupes_fixes else "Non")
    ttk.Combobox(frame, textvariable=groupes_var, values=["Oui", "Non"], state="readonly").grid(row=row, column=1, sticky="w")
    row += 1

    entry_places = champ_avec_label("Places disponibles :", "", row, tp.places if is_edit else None)
    row += 1
    entry_decalage=champ_avec_label("Décalage du début des TP (en semaines) :", "", row, tp.decalage_semaines if is_edit else 0)
    row += 1

    # Alternance fixe
    tk.Label(frame, text="Alternance fixe :").grid(row=row, column=0, sticky="w")
    alternance_var = tk.StringVar(value="Oui" if not is_edit or tp.alternance_fixe else "Non")
    ttk.Combobox(frame, textvariable=alternance_var, values=["Oui", "Non"], state="readonly").grid(row=row, column=1, sticky="w")
    row += 1

    def enregistrer_tp():
        nom = entry_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Nom requis")
            return
        if not periodes:
            messagebox.showerror("Erreur", "Ajoutez au moins une période")
            return
        try:
            places = int(entry_places.get())
            decalage=int(entry_decalage.get())
        except ValueError:
            messagebox.showerror("Erreur", "Valeur numérique invalide")
            return

        if is_edit:
            tp.nom = nom
            tp.periodes = periodes.copy()
            tp.groupes_fixes = (groupes_var.get() == "Oui")
            tp.places = places
            tp.alternance_fixe = (alternance_var.get() == "Oui")
            tp.decalage_semaines=decalage
        else:
            t_id = str(app.id)
            app.id += 1
            from classesColloscopeAuto import TP as TPClass
            nouveau_tp = TPClass(
                id=t_id,
                nom=nom,
                classe=classe,
                periodes=periodes.copy(),
                horaires=[],  # à ajouter séparément si besoin
                groupes_fixes=(groupes_var.get() == "Oui"),
                places=places,
                alternance_fixe=(alternance_var.get() == "Oui"),
                decalage_semaines=decalage
            )
            app.db['TPs'][t_id] = nouveau_tp
            classe.TP.append(nouveau_tp)


        construire_arborescence_gauche(treeview, app)
        messagebox.showinfo("Succès", "TP/TD enregistré.")
        _formulaire_tp(app, frame, treeview, classe_id, tp=tp if is_edit else nouveau_tp)

    def supprimer_tp():
        if not is_edit:
            return
        confirm = messagebox.askyesno("Confirmation", "Supprimer ce TP/TD ?")
        if confirm:
            classe.TP.remove(tp)
            del app.db['TPs'][tp.id]

            construire_arborescence_gauche(treeview, app)
            messagebox.showinfo("Supprimé", "TP/TD supprimé.")
            for widget in frame.winfo_children():
                widget.destroy()

    if is_edit:
        tk.Button(frame, text="Modifier", command=enregistrer_tp).grid(row=row, column=0, pady=10)
        tk.Button(frame, text="Supprimer", command=supprimer_tp).grid(row=row, column=1, pady=10)
    else:
        tk.Button(frame, text="Valider", command=enregistrer_tp).grid(row=row, column=0, columnspan=2, pady=10)


def afficher_formulaire_creation_etudiant(app, frame, treeview, classe_id):
    _formulaire_etudiant(app, frame, treeview, classe_id, etu=None)

def afficher_formulaire_edition_etudiant(app, frame, treeview, classe_id, etudiant_id):
    etu = app.db['etudiants'][etudiant_id]
    _formulaire_etudiant(app, frame, treeview, classe_id, etu=etu)

def afficher_formulaire_creation_etudiant(app, frame, treeview, classe_id):
    _formulaire_etudiant(app, frame, treeview, classe_id, etu=None)

def afficher_formulaire_edition_etudiant(app, frame, treeview, classe_id, etudiant_id):
    etu = app.db['etudiants'][etudiant_id]
    _formulaire_etudiant(app, frame, treeview, classe_id, etu=etu)

def _formulaire_etudiant(app, frame, treeview, classe_id, etu=None):
    for widget in frame.winfo_children():
        widget.destroy()

    app.help_text = "Vous pouvez ajouter les étudiants un à un, mais vous pouvez également tous les importer (y compris ceux d'autres classes) depuis un fichier .csv. Attention au format attendu : le séparateur est le point virgule, l'encodage est utf-8, la première colonne contient le nom/prénom de l'étudiant, la deuxième colonne contient le nom de la classe (attention aux fautes de frappes), la troisième colonne contient la liste des options de l'étudiant, séparées par une virgule (inutile d'ajouter l'option de base avec le nom de la classe, elle est automatiquement ajoutée), et enfin la quatrième colonne contient le numéro du groupe de colle."
    mettre_a_jour_aide(app)

    classe = app.db['classes'][classe_id]
    is_edit = etu is not None

    row = 0
    tk.Label(frame, text="Nom prénom de l'étudiant :").grid(row=row, column=0, sticky="w")
    entry_nom = tk.Entry(frame)
    if is_edit:
        entry_nom.insert(0, etu.nom)
    entry_nom.grid(row=row, column=1, sticky="w")
    row += 1

    tk.Label(frame, text="Groupe de colle :").grid(row=row, column=0, sticky="w")
    entry_groupe = tk.Entry(frame)
    if is_edit:
        entry_groupe.insert(0, str(etu.groupe))
    entry_groupe.grid(row=row, column=1, sticky="w")
    row += 1

    autres_options = [opt for opt in classe.options if opt != classe.nom]
    listbox_options = None

    if autres_options:
        tk.Label(frame, text="Options supplémentaires :").grid(row=row, column=0, sticky="nw")
        listbox_options = tk.Listbox(frame, selectmode="multiple", exportselection=False, height=6)
        for i, opt in enumerate(autres_options):
            listbox_options.insert(tk.END, opt)
            if is_edit and opt in etu.options:
                listbox_options.selection_set(i)
        listbox_options.grid(row=row, column=1, sticky="w")
        row += 1

    def enregistrer():
        nom = entry_nom.get().strip()
        if not nom:
            messagebox.showerror("Erreur", "Le nom est requis.")
            return

        try:
            groupe = int(entry_groupe.get())
        except ValueError:
            messagebox.showerror("Erreur", "Le groupe doit être un entier.")
            return

        selected_options = [classe.nom]
        if listbox_options:
            selected_options += [autres_options[i] for i in listbox_options.curselection()]

        if is_edit:
            etu.nom = nom
            etu.groupe = groupe
            etu.options = selected_options
        else:
            e_id = str(app.id)
            app.id += 1
            nouveau = etudiant(e_id, nom, classe, groupe, selected_options)
            app.db['etudiants'][e_id] = nouveau
            classe.etudiants.append(nouveau)

        construire_arborescence_gauche(treeview, app)
        messagebox.showinfo("Succès", "Étudiant enregistré.")

    def supprimer():
        if not is_edit:
            return
        confirm = messagebox.askyesno("Confirmation", "Supprimer cet étudiant ?")
        if confirm:
            classe.etudiants.remove(etu)
            del app.db['etudiants'][etu.id]
            construire_arborescence_gauche(treeview, app)
            messagebox.showinfo("Supprimé", "Étudiant supprimé.")
            for widget in frame.winfo_children():
                widget.destroy()

    def importer_csv():
        path = filedialog.askopenfilename(filetypes=[("Fichier CSV", "*.csv")])
        if not path:
            return

        with open(path, encoding='utf-8') as f:
            reader = csv.reader(f, delimiter=';')
            for line in reader:
                if len(line) < 4:
                    continue
                nom, classe_nom, opt_str, groupe_str = line[0].strip(), line[1].strip(), line[2].strip(), line[3].strip()
                classe_cible = next((c for c in app.db['classes'].values() if c.nom == classe_nom), None)
                if not classe_cible:
                    continue
                options = [o.strip() for o in opt_str.split(',') if o.strip()]
                if classe_cible.nom not in options:
                    options.append(classe_cible.nom)
                try:
                    groupe = int(groupe_str)
                except:
                    continue
                e_id = str(app.id)
                app.id += 1
                nouveau = etudiant(e_id, nom, classe_cible, groupe, options)
                app.db['etudiants'][e_id] = nouveau
                classe_cible.etudiants.append(nouveau)


        construire_arborescence_gauche(treeview, app)
        messagebox.showinfo("Importation réussie", "Les étudiants ont été importés.")

    tk.Button(frame, text="Importer depuis un CSV", command=importer_csv).grid(row=row, column=0, columnspan=2, pady=10)
    row += 1

    if is_edit:
        tk.Button(frame, text="Modifier", command=enregistrer).grid(row=row, column=0, pady=10)
        tk.Button(frame, text="Supprimer", command=supprimer).grid(row=row, column=1, pady=10)
    else:
        tk.Button(frame, text="Valider", command=enregistrer).grid(row=row, column=0, columnspan=2, pady=10)

# Liste des jours de la semaine
JOURS_SEMAINE = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi"]

def creation_horaire_classe(app, frame, treeview, cls):
    app.help_text = "Vous pouvez ici ajouter des contraintes d'emploi du temps pour des options spécifiques. Il est inutile d'ajouter des contraintes qui s'appliquent à tous les étudiants, car normalement vous en avez déjà tenu compte pour les horaires des colleurs ! Par contre, vous pouvez par exemple ajouter les heures de LV2 (si certains horaires de colles ont lieu à ce moment) afin que les étudiants avec cette option ne se voient pas affectés à des créneaux de colles qui engendreraient des conflits avec leur option. Vous pouvez également gérer ainsi des TP/TD dont l'alternance est fixée (1 semaine groupe 1, 1 semaine groupe 2 par exemple), mais il faut avoir préalablement défini des options correspondantes.\n Attention de bien remplir la durée en minutes, et de bien choisir les semaines pour lesquelles la contrainte s'applique."
    mettre_a_jour_aide(app)

    afficher_formulaire_horaire(app, frame, treeview, mode="classe", obj=cls,cls=cls)

def edition_horaire_classe(app, frame, treeview, cls, horaire):
    app.help_text = "Vous pouvez modifier la contrainte d'edt ici."
    mettre_a_jour_aide(app)

    afficher_formulaire_horaire(app, frame, treeview, mode="classe", obj=cls,cls=cls, horaire_existant=horaire)

def creation_horaire_tp(app, frame, treeview, tp):
    app.help_text = "Vous pouvez ajouter un horaire pour le TP/TD ici. Attention de bien remplir la durée en minutes et de bien respecter le format pour le début de l'horaire. Choisissez également les semaines pour lesquelles cet horaire est diponible et le nombre de places disponibles pour cet horaire."
    mettre_a_jour_aide(app)
    afficher_formulaire_horaire(app, frame, treeview, mode="tp", obj=tp,cls=tp.classe)

def edition_horaire_tp(app, frame, treeview, tp, horaire):
    app.help_text = "Vous pouvez modifier l'horaire ici."
    mettre_a_jour_aide(app)
    afficher_formulaire_horaire(app, frame, treeview, mode="tp", obj=tp,cls=tp.classe, horaire_existant=horaire)

def creation_horaire_colleur(app, frame, treeview, colleur,matiere_courante):
    app.help_text = "Vous pouvez ajouter des horaires au colleur ici. Attention au format pour le début de l'horaire et à la durée qui doit être exprimée en minutes. La durée correspond bien à la durée totale de la colle (passage + préparation éventuelle), normalement c'est la même que celle que vous avez déjà rempli pour la matière.\n Vous pouvez également choisir d'affecter cet horaire à une autre classe/matière si le colleur colle dans plusieurs classes, ce qui permet plus de flexibilité dans les affectations.\n Vous devez choisir les semaines où cet horaire est disponible (vous pouvez donc créer des horaires différenciés par semestre par exemple). Une alerte s'affiche si vous choisissez des semaines où le jour correspondant est férié, cela n'a pas d'impact sur la résolution (vous pouvez donc laisser tel quel) mais cela vous permet d'anticiper les éventuels déplacements de colles dès la conception du colloscope, par exemple en recréant un horaire de substitution les semaines où le jour choisi est férié et en décochant les semaines avec jours fériés pour l'horaire principal.\n Le paramètre 'horaire flexible' permet de savoir si cet horaire est celui qui doit être supprimé quand le colleur a un nombre d'heures non entier dans la matière. Par exemple si le colleur donne 1.5 heures dans la matière, vous allez créer au moins deux horaires pour le colleur, et une semaine sur deux l'horaire flexible disparaître. Vous pouvez également mettre tous les horaires en flexible, et laisser le programme décider à chaque fois lequel doit disparaître.\n Le nombre de places disponibles est pré-rempli avec le paramètre correspondant de la matière, et ne devrait pas être changé a priori (mais la possibilité existe au cas où des situations exceptionnelles l'exigerait)."
    mettre_a_jour_aide(app)
    afficher_formulaire_horaire(app, frame, treeview, mode="colleur", obj=colleur, cls=matiere_courante.classe,matiere_courante=matiere_courante)

def edition_horaire_colleur(app, frame, treeview, colleur, horaire,matiere_courante):
    app.help_text = "Vous pouvez modifier l'horaire ici"
    mettre_a_jour_aide(app)
    afficher_formulaire_horaire(app, frame, treeview, mode="colleur", obj=colleur,cls=matiere_courante.classe, horaire_existant=horaire,matiere_courante=matiere_courante)

def afficher_formulaire_horaire(app, frame, treeview, mode, obj, cls, horaire_existant=None,matiere_courante=None):
    is_edit = horaire_existant is not None

    for widget in frame.winfo_children():
        widget.destroy()



    row = 0
    tk.Label(frame, text="Jour :").grid(row=row, column=0, sticky="w")
    jour_var = tk.StringVar()
    jour_menu = tk.OptionMenu(frame, jour_var, *JOURS_SEMAINE)
    jour_menu.grid(row=row, column=1, sticky="w")

    row += 1
    tk.Label(frame, text="Heure de début (HH:MM) :").grid(row=row, column=0, sticky="w")
    entree_heure = tk.Entry(frame)
    entree_heure.grid(row=row, column=1, sticky="w")

    row += 1
    tk.Label(frame, text="Durée (en minutes) :").grid(row=row, column=0, sticky="w")
    entree_duree = tk.Entry(frame)
    entree_duree.grid(row=row, column=1, sticky="w")

    row += 1

    semaines_vars = {}
    semaines_cours = cls.semaines_cours
    semaines_colles = cls.semaines_colles

    def get_semaine_buttons(semaines):

        buttons = []
        dico_semaines = app.db["calendrier"].get_all_semaines()

        for i, s in enumerate(semaines):
            var = tk.BooleanVar()
            semaines_vars[s] = var

            d, f = dico_semaines.get(s, (None, None))
            if d and f:
                texte = f"Semaine {s} : du {d.strftime('%d/%m')} au {f.strftime('%d/%m')}"
            else:
                texte = f"Semaine {s}"

            cb = tk.Checkbutton(semaine_frame, text=texte, variable=var)
            cb.grid(row=i // 2, column=i % 2, sticky="w", padx=5, pady=2)
            buttons.append(cb)

        return buttons

    semaine_frame = tk.LabelFrame(frame, text="Semaines")
    semaine_frame.grid(row=row, column=0, columnspan=5, sticky="ew", pady=10)

    if mode in ("classe", "tp"):
        semaines = semaines_cours
        get_semaine_buttons(semaines)

        def select_semaine_A():
            for i, s in enumerate(semaines):
                semaines_vars[s].set(i % 2 == 0)

        def select_semaine_B():
            for i, s in enumerate(semaines):
                semaines_vars[s].set(i % 2 == 1)

        # Cadre pour les boutons de sélection
        bouton_frame = tk.Frame(semaine_frame)
        nb_lignes_semaines = (len(semaines) + 1) // 2
        bouton_frame.grid(row=nb_lignes_semaines, column=0, columnspan=2, pady=(10, 0), sticky="w")

        # Boutons côte à côte avec grid dans bouton_frame
        tk.Button(bouton_frame, text="Tout cocher", command=lambda: [v.set(True) for v in semaines_vars.values()]).grid(row=0, column=0, padx=5)
        tk.Button(bouton_frame, text="Tout décocher", command=lambda: [v.set(False) for v in semaines_vars.values()]).grid(row=0, column=1, padx=5)
        tk.Button(bouton_frame, text="Semaine A", command=select_semaine_A).grid(row=0, column=2, padx=5)
        tk.Button(bouton_frame, text="Semaine B", command=select_semaine_B).grid(row=0, column=3, padx=5)

    elif mode == "colleur":
        semaines = semaines_colles
        get_semaine_buttons(semaines)
        # Boutons tout cocher / tout décocher pour les semaines de colles
        bouton_frame = tk.Frame(semaine_frame)
        bouton_frame.grid(row=100, column=0, columnspan=2, pady=(10, 0))  # ligne très en bas pour éviter les collisions

        tk.Button(bouton_frame, text="Tout cocher", command=lambda: [semaines_vars[s].set(True) for s in semaines]).grid(row=0, column=0, padx=5)
        tk.Button(bouton_frame, text="Tout décocher", command=lambda: [semaines_vars[s].set(False) for s in semaines]).grid(row=0, column=1, padx=5)
        jour_warning = tk.Label(frame, text="", fg="red")
        jour_warning.grid(row=row+5, column=0, columnspan=5)

        def update_warning():
            jour = jour_var.get()
            mauvaises = []
            for s in semaines:
                if app.db['calendrier'].est_chome(jour, s):
                    d, f = app.db['calendrier'].get_all_semaines().get(s, (None, None))
                    if d and f:
                        texte = f"Semaine {s} : du {d.strftime('%d/%m')} au {f.strftime('%d/%m')} (⚠ jour férié)"
                    else:
                        texte = f"Semaine {s} (⚠ jour férié)"
                    mauvaises.append(texte)

            if mauvaises:
                jour_warning.config(text="\n".join(mauvaises))
            else:
                jour_warning.config(text="")

        jour_var.trace_add("write", lambda *args: update_warning())

    if mode == "classe":
        tk.Label(frame, text="Options concernées :").grid(row=row+6, column=0, sticky="w")
        options_vars = {}
        for i, opt in enumerate(obj.options):
            var = tk.BooleanVar()
            cb = tk.Checkbutton(frame, text=opt, variable=var)
            cb.grid(row=row+7+i//4, column=(i % 4), sticky="w")
            options_vars[opt] = var

    if mode == "tp":
        tk.Label(frame, text=f"Nombre de places (par défaut {obj.places}) :").grid(row=row+6, column=0, sticky="w")
        entree_places = tk.Entry(frame)
        entree_places.insert(0, str(obj.places))
        entree_places.grid(row=row+6, column=1, sticky="w")

    if mode == "colleur":
        mat = matiere_courante
        entree_duree.delete(0, tk.END)
        entree_duree.insert(0, str(mat.dureeColle))

        tk.Label(frame, text=f"Nombre de places (par défaut {mat.places}) :").grid(row=row+6, column=0, sticky="w")
        entree_places = tk.Entry(frame)
        entree_places.insert(0, str(mat.places))
        entree_places.grid(row=row+6, column=1, sticky="w")

        tk.Label(frame, text=f"Salle :").grid(row=row+7, column=0, sticky="w")
        entree_salle = tk.Entry(frame)
        entree_salle.grid(row=row+7, column=1, sticky="w")

        var_flexible = tk.BooleanVar()
        tk.Checkbutton(frame, text="Horaire flexible", variable=var_flexible).grid(row=row+8, column=0, sticky="w")



        tk.Label(frame, text="Matières affectées :").grid(row=row+9, column=0, sticky="w")
        matiere_vars = {}
        for i, m in enumerate(obj.matieres):
            var = tk.BooleanVar(value=(m == mat))
            cb = tk.Checkbutton(frame, text=m.nom+" "+m.classe.nom, variable=var)
            cb.grid(row=row+10+i//4, column=(i % 4), sticky="w")
            matiere_vars[m] = var

    if is_edit:
        jour_var.set(horaire_existant.jour)
        h = horaire_existant.debut // 60
        m = horaire_existant.debut % 60
        entree_heure.delete(0, tk.END)
        entree_heure.insert(0, f"{h:02d}:{m:02d}")
        entree_duree.delete(0, tk.END)
        entree_duree.insert(0, str(horaire_existant.duree))
        for s in horaire_existant.semaines:
            if s in semaines_vars:
                semaines_vars[s].set(True)

        if mode == "classe":
            for opt in horaire_existant.options:
                if opt in options_vars:
                    options_vars[opt].set(True)

        if mode == "tp":
            entree_places.delete(0, tk.END)
            entree_places.insert(0, str(horaire_existant.places))

        if mode == "colleur":
            entree_places.delete(0, tk.END)
            entree_places.insert(0, str(horaire_existant.places))
            entree_salle.delete(0,tk.END)
            entree_salle.insert(0,horaire_existant.salle)
            var_flexible.set(horaire_existant.flexible)
            for m in horaire_existant.matieres:
                if m in matiere_vars:
                    matiere_vars[m].set(True)
                else:
                    matiere_vars[m].set(False)

    def valider():
        try:
            jour = jour_var.get()
            if jour not in JOURS_SEMAINE:
                raise ValueError("Jour invalide")

            debut = entree_heure.get()
            h, m = map(int, debut.strip().split(":"))
            debut_minutes = h * 60 + m

            duree = int(entree_duree.get())

            semaines_selectionnees = [s for s, var in semaines_vars.items() if var.get()]
            if not semaines_selectionnees:
                raise ValueError("Aucune semaine sélectionnée")

            # Initialisation des champs spécifiques
            options = []
            matieres = []
            places = 0
            colleur = None
            flexible = False
            salle=""

            if mode == "classe":
                options = [opt for opt, var in options_vars.items() if var.get()]
            elif mode == "tp":
                options = obj.options
                matieres = [obj]
                places = int(entree_places.get())
            elif mode == "colleur":
                flexible = var_flexible.get()
                matieres = [m for m, var in matiere_vars.items() if var.get()]
                if not matieres:
                    raise ValueError("Vous devez sélectionner au moins une matière")
                options = list(set(opt for m in matieres for opt in m.options))
                places = int(entree_places.get())
                salle=entree_salle.get()
                colleur = obj

            if is_edit:
                h = horaire_existant
                h.jour = jour
                h.debut = debut_minutes
                h.duree = duree
                h.semaines = semaines_selectionnees
                h.options = options
                h.matieres = matieres
                h.places = places
                h.colleur = colleur
                h.flexible = flexible
                h.salle=salle
                if h.id not in app.db['horaires']:
                    app.db['horaires'][h.id] = h
            else:
                h = horaire(
                    id=str(app.id),
                    jour=jour,
                    debut=debut_minutes,
                    duree=duree,
                    semaines=semaines_selectionnees,
                    flexible=flexible,
                    matieres=matieres,
                    options=options,
                    places=places,
                    colleur=colleur,
                    salle=salle
                )
                app.db['horaires'][str(app.id)] = h
                if mode == "classe":
                    obj.edt.append(h)
                elif mode == "tp":
                    obj.horaires.append(h)
                elif mode == "colleur":
                    obj.horaires.append(h)
                app.id += 1

            messagebox.showinfo("Succès", "Horaire enregistré avec succès !")
            construire_arborescence_gauche(treeview, app)

        except Exception as e:
            messagebox.showerror("Erreur", f"Erreur : {str(e)}")

    bouton_texte = "Modifier" if is_edit else "Valider"
    tk.Button(frame, text=bouton_texte, command=valider).grid(row=100, column=0, pady=10)

    if is_edit:
            def supprimer():
                if messagebox.askyesno("Confirmation", "Supprimer cet horaire ?"):
                    # Suppression du conteneur spécifique
                    if mode == "classe":
                        obj.edt.remove(horaire_existant)
                    elif mode in ("tp", "colleur"):
                        obj.horaires.remove(horaire_existant)

                    # Suppression de app.db["horaires"]
                    del app.db["horaires"][horaire_existant.id]

                    messagebox.showinfo("Suppression", "Horaire supprimé avec succès.")
                    construire_arborescence_gauche(treeview, app)

            bouton_supprimer = tk.Button(frame, text="🗑️ Supprimer l'horaire", fg="red", command=supprimer)
            bouton_supprimer.grid(row=999, column=0, columnspan=2, pady=10)

#%% Main

if __name__=='__main__':
    app = ApplicationState()
    root = tk.Tk()
    fenetre_accueil(root, app)
    root.mainloop()