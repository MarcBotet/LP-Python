#!/usr/bin/python3

from ast import literal_eval
from datetime import timedelta, datetime
from math import radians, cos, sin, atan2, sqrt
import argparse
import urllib.request
import xml.etree.ElementTree as ET
import unicodedata
import webbrowser

urlbicing = "http://wservice.viabicing.cat/getstations.php?v=1"
urlevent = "http://www.bcn.cat/tercerlloc/agenda_cultural.xml"
urlparking = "http://www.bcn.cat/tercerlloc/Aparcaments.xml"


def normalitzaString(s):
    return (''.join((c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn'))).lower()


def readXML(url):
    sock = urllib.request.urlopen(url)
    xml = ET.fromstring(sock.read())
    sock.close()
    return xml


def stringToData(d):
    day, month, year = d.split('/')
    date = datetime(int(year), int(month), int(day))
    return date

def stringToDataHour(d,hour):
    h, m = hour.split(":")
    date = d.replace(hour=int(h), minute=int(m))
    return date


class Esdeveniment:
    def __init__(self,nom, dist, barri, city, address, pos,dia,hour,bicings,aparcaments,bicingsBuits):
        self.nom = nom
        self.address = address+", "+barri
        self.barri = barri
        self.dist = dist
        self.city = city
        self.dia = stringToDataHour(dia,hour)
        self.pos = pos
        self.bicings = bicings
        self.bicingsBuits = bicingsBuits
        self.aparcaments = aparcaments

def getEsdeveniments(key, keyData, filtres, dies):
    xml = readXML(urlevent)
    x = 0
    TAGS = ("item/name", "item/addresses/item/district", "item/addresses/item/barri",
            "item/addresses/item/city", "item/addresses/item/address",
            "item/addresses/item/gmapx", "item/addresses/item/gmapy","item/proxhour")

    esdeveniments = []

    for rows in xml.find("search/queryresponse/list/list_items"):
        try:
            nom, dist, barri, city, address, gmapx, gmapy,hour = map(lambda x: rows.findtext(x), TAGS)
            begindates = rows.findtext("item/begindate")
            enddates = rows.findtext("item/enddate")
            nextdate = rows.findtext("item/proxdate")
            nextdate = stringToData(nextdate)
            cons = Consulta(nom, dist, barri, city, address)
            if dies:
                begindate = stringToData(begindates)
                enddate = stringToData(enddates)
                data = DataConsulta(begindate, enddate,nextdate)
            if filtres and dies:
                if data.eval_expr(keyData) and cons.eval_expression(key):
                    pos = Posicio(gmapx, gmapy)
                    esdeveniments.append(Esdeveniment(nom, dist, barri, city, address, pos,nextdate,hour,[],[],[]))
                    x += 1
            elif not dies and filtres:
                if cons.eval_expression(key):
                    pos = Posicio(gmapx, gmapy)
                    esdeveniments.append(Esdeveniment(nom, dist, barri, city, address, pos, nextdate, hour,[],[],[]))
                    x += 1
            elif dies and not filtres:
                if data.eval_expr(keyData):
                    pos = Posicio(gmapx,gmapy)
                    esdeveniments.append(Esdeveniment(nom, dist, barri, city, address, pos, nextdate, hour,[],[],[]))
                    x += 1
            else:
                pos = Posicio(gmapx, gmapy)
                esdeveniments.append(Esdeveniment(nom, dist, barri, city, address, pos, nextdate, hour,[],[],[]))
        except:
            continue

    esdeveniments.sort(key=lambda r: r.dia)
    return esdeveniments




class DataConsulta:
    def __init__(self, begindate, enddate,nextdate):
        self.begindate = begindate
        self.enddate = enddate
        self.nextdate = nextdate

    def eval_expr(self, expr):
        if isinstance(expr, str):
            date = stringToData(expr)
            return (self.begindate <= date <= self.enddate) or (self.nextdate == date)
        elif isinstance(expr, tuple):
            return self.exprTuple(expr)
        elif isinstance(expr, list):
            return any(self.eval_expr(subExpr) for subExpr in expr)
        return False

    def exprTuple(self, expr):
        sdata, menys, mes = expr
        date = stringToData(sdata)
        datemenys = date
        datemes = date
        d = timedelta(days=menys)
        datemenys +=d
        d = timedelta(days=mes)
        datemes += d
        return ((self.begindate <= date <= self.enddate) or (self.begindate <= datemenys <= self.enddate)
                or (self.begindate <= datemes <= self.enddate) or (self.nextdate == date) or (self.nextdate == datemes)
                or (self.nextdate == datemenys))

class Consulta():
    def __init__(self, nom, dist, barri, city, comarca):
        self.nom = nom
        self.dist = dist
        self.barri = barri
        self.city = city
        self.comarca = comarca

    def eval_expression(self, consulta):
        if isinstance(consulta, str):
            # base
            return self.cerca(normalitzaString(consulta))
        elif isinstance(consulta, tuple):
            # or
            return any(self.eval_expression(subCons) for subCons in consulta)
        elif isinstance(consulta, list):
            # and
            return all(self.eval_expression(subCons) for subCons in consulta)
        return False

    def cerca(self, claus):
        if claus in normalitzaString(self.nom): return True
        if claus in normalitzaString(self.dist): return True
        if claus in normalitzaString(self.barri): return True
        if claus in normalitzaString(self.city): return True
        if claus in normalitzaString(self.comarca): return True
        return False

class Posicio:

    RADI_TERRA = 6371000

    def __init__(self, latitud, longitud):
        self.latitud, self.longitud = map(radians, (float(latitud), float(longitud)))

    # En metres
    def distancia(self, altra):
        dlon = self.longitud - altra.longitud
        dlat = self.latitud - altra.latitud

        a = sin(dlat / 2) ** 2 + cos(altra.longitud) * cos(self.longitud) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return Posicio.RADI_TERRA * c

class Bicing:

    def __init__(self, posicio, carrer, numero, bicis,slots):
        self.pos,self.bicis,self.slots = (posicio,bicis,slots)
        self.carrer = carrer +" "+numero

class Aparcament:

    def __init__(self, name,posicio, address, barri):
        self.name, self.pos= (name,posicio)
        self.address = address+", "+barri

def getBicings():

    TAGS = ("lat", "long", "street", "streetNumber", "bikes", "status","slots")

    arbreXml = readXML(urlbicing)

    bicings = []
    bicingsAparcaments = []
    for i in range(1, len(arbreXml)):
        estacio = arbreXml[i]
        latitud, longitud, carrer, numero, bicis, estat,slots = map(lambda x: estacio.findtext(x), TAGS)

        if estat == "OPN" and (int(bicis) > 0):
            bicings.append(Bicing(Posicio(latitud, longitud), carrer, numero, bicis,slots))
        if estat == "OPN" and (int(slots) > 0):
            bicingsAparcaments.append(Bicing(Posicio(latitud, longitud), carrer, numero, bicis,slots))
    return (bicings,bicingsAparcaments)

def getAparcaments():
    xml = readXML(urlparking)
    TAGS = ("item/name","item/addresses/item/gmapx", "item/addresses/item/gmapy", "item/addresses/item/barri",
            "item/addresses/item/address")

    aparcaments = []

    for rows in xml.find("search/queryresponse/list/list_items"):
        try:
            name,gmapx, gmapy,barri,address = map(lambda x: rows.findtext(x), TAGS)
            if not isinstance(gmapx,str): continue
            p = Posicio(gmapx,gmapy)
            aparcaments.append(Aparcament(name,p,address,barri))
        except:
            continue

    return aparcaments


def bicingsAprop(esdeveniments,bicings):
    for e in esdeveniments:
        parades = []
        for b in bicings:
            pe = e.pos
            pb = b.pos
            dis = pe.distancia(pb)
            if dis <= 500:
                i = (b,dis)
                parades.append(i)
        if len(parades) > 0: parades.sort(key=lambda tup: tup[1])
        e.bicings = parades


def bicingsBuitsAprop(esdeveniments,bicingsBuits):
    for e in esdeveniments:
        parades = []
        for b in bicingsBuits:
            pe = e.pos
            pb = b.pos
            dis = pe.distancia(pb)
            if dis <= 500:
                i = (b,dis)
                parades.append(i)
        if len(parades) > 0: parades.sort(key=lambda tup: tup[1])
        e.bicingsBuits = parades

def aparcamentsAprop(esdeveniments,aparcaments):
    for e in esdeveniments:
        aparc = []
        for b in aparcaments:
            pe = e.pos
            pb = b.pos
            dis = pe.distancia(pb)
            if dis <= 500:
                i = (b,dis)
                aparc.append(i)
        if len(aparc) > 0: aparc.sort(key=lambda tup: tup[1])
        e.aparcaments = aparc

class TaulaHtml(object):
    # constructor
    def __init__(self, acts):
        self.acts = acts

    # escriu una fila de la taula, corresponent a una activitat
    def escriu_fila_taula_html(self, act, ifile,even):
        color = "#ddd" if even else "#eee"
        rows = 5
        ifile.write("""      <tr style="background-color:{};border-bottom:1px solid black">
                <td rowspan="{}" style="border-bottom:1px solid black">{}</td>
                <td rowspan="{}" style="border-bottom:1px solid black">{}</td>
                <td rowspan="{}" style="border-bottom:1px solid black">{}</td>
              </tr>
        """.format(color,rows + 1, act.nom, rows + 1, act.address, rows + 1, act.dia))

        i = 0
        while i < rows:
            ifile.write("      <tr style='background-color:{}'>\n".format(color))
            ifile.write("        <td>{}</td>\n".format(
                act.bicingsBuits[i][0].carrer if i < len(act.bicingsBuits) else ""))
            ifile.write("        <td style='text-align:center'>{}</td>\n".format(
                act.bicingsBuits[i][0].slots if i < len(act.bicingsBuits) else ""))
            ifile.write("        <td>{}</td>\n".format(
                act.bicings[i][0].carrer if i < len(act.bicings) else ""))
            ifile.write("        <td style='text-align:center'>{}</td>\n".format(
                act.bicings[i][0].bicis if i < len(act.bicings) else ""))
            ifile.write("        <td>{}</td>\n".format(
                act.aparcaments[i][0].name if i < len(act.aparcaments) else ""))
            ifile.write("        <td style='text-align:center'>{}</td>\n".format(
                act.aparcaments[i][0].address if i < len(act.aparcaments) else ""))
            ifile.write("      </tr>\n")
            i += 1

    # escriu la taula html d'activitats en el fitxer 'table.html'
    def escriu(self):
        file_name = "Activitats.html"
        ifile = open(file_name, "w")
        ifile.write("""<!DOCTYPE html>
<html>
  <head>
    <title>Practica Python LP - Activitats</title>
    <meta charset="UTF-8" />
    <style>
      html { font-family:Arial }
      table { border-top:1px solid black;border-bottom:1px solid black }
      th { font-size:20px;color:#fff;border-left:1px solid black;border-right:1px solid black;border-bottom:1px solid black }
      td { font-size:12px;border-left:1px solid black;border-right:1px solid black;padding:5px }
    </style>
  </head>
  <body>
    <table style="width:100%;border-collapse:collapse">
      <colgroup style="width:20%"></colgroup>
      <colgroup></colgroup>
      <colgroup></colgroup>
      <colgroup span="2"></colgroup>
      <colgroup span="2"></colgroup>
      <colgroup span="2"></colgroup>
      <tr style="background-color:#88f">
        <th rowspan="2" style="padding-top:20px;padding-bottom:20px">Nom activitat</th>
        <th rowspan="2">Adreça</th>
        <th rowspan="2">Data</th>
        <th colspan="2">Bicings buits</th>
        <th colspan="2">Bicings amb bicis</th>
        <th colspan="2">Aparcaments</th>
      </tr>
      <tr style="background-color:#88f">
        <th style="font-size:16px">Adreça</th>
        <th style="font-size:16px">Llocs</th>
        <th style="font-size:16px">Adreça</th>
        <th style="font-size:16px">Bicis</th>
        <th style="font-size:16px">Nom</th>
        <th style="font-size:16px">Adreça</th>
      </tr>
""")
        even = True
        for act in self.acts:
            self.escriu_fila_taula_html(act, ifile,even)
            even = not even
        ifile.write("""    </table>
  </body>
</html>""")
        ifile.close()
        webbrowser.open(file_name)

parser = argparse.ArgumentParser()
parser.add_argument("--date", help="Introdueix la data o les dates desitjades")
parser.add_argument("--key", help="Introdueix el tipus d'activitat o localització")
args1 = parser.parse_args()
args = vars(parser.parse_args())
filtres = False
dies = False
dates = ""
claus = ""
if args1.date:
    dies = True
    dates = literal_eval(args["date"])
if args1.key:
    filtres = True
    claus = literal_eval(args["key"])

esdeveniments = getEsdeveniments(claus, dates, filtres, dies)
bicings,bicingsAparcaments = getBicings()
aparcaments = getAparcaments()
bicingsAprop(esdeveniments,bicings)
bicingsBuitsAprop(esdeveniments,bicingsAparcaments)
aparcamentsAprop(esdeveniments,aparcaments)
TaulaHtml(esdeveniments).escriu()







