import json


class TestCaseReclamationClient:
    def __init__(self, config_path='param.json'):
        with open(config_path, 'r') as file:
            config = json.load(file)
        self.login = config['login']
        self.password = config['password']
        self.url = config['url']
        self.CDT_3668 = f"""1. Open the URL: {self.url}
2. Enter {self.login} into the login field
3. Enter {self.password} into the password field
4. Click the Login button
5. Go to: {self.url}/Satisfaction%20client/ReclamationClient/ReclamationClt.aspx
6. Click on Ajouter
7. Check this message is visible: Fiche Réclamation client N° Enregistrée par (Name of  user) ( )
8. Check this message is visible: Enregistrement"""

        self.CDT_3681 = f"""1. Open the URL: {self.url}
2. Enter "{self.login}" into the login field
3. Enter "{self.password}" into the password field
4. Click the "Login" button
5. Navigate to: {self.url}/Satisfaction%20client/ReclamationClient/ReclamationClt.aspx
6. Click on "Ajouter"
7. Fill in all the fields in the form **except the date field**"""

        steps_common = """
Enter Reclamation Description any random sentence
The user clicks another "Sélectionner" button, this time to choose a "Réceptionnaire."of index is 134
They wait for a table listing potential recipients to appear.
The user clicks on a '210892' within this table of  index  44. 
Select Client:
The user clicks a button labeled "Sélectionner" (Select) to choose a client of index  132.
They wait for a table listing clients to appear
The user then clicks on a specific client's entry in the table 
Select the option labeled any option from the dropdown menu located at index 136.
Enter Invoice or Delivery Note Number: The user types the relevant invoice or delivery note number into a text field.
Select Severity of Reclamation: The user chooses an option from the "Gravité Réclamation" (Severity of Reclamation) dropdown.
Check "Avec retour client" (With Customer Return)
Submit Reclamation: Finally, the user clicks the "Envoyer" (Send/Submit) button to submit the reclamation
"""
        self.CDT_3669 = self.CDT_3668 + steps_common
        self.CDT_3684 = self.CDT_3668 + steps_common
        self.CDT_3686 = self.CDT_3668 + steps_common + "Check if any element contains text matching the pattern En attente de déclenchement d'une fiche PNC' with  color red  and  show in  logs"
        self.CDT_3687 = self.CDT_3668 + steps_common + """Check if any element contains text matching the pattern 'Enregistrement'
'Liste des produits'
'Liste des types de causes'
'Liste des non-conformités'
'Liste des demandes parties intéressées'"""
        self.CDT_3688 = self.CDT_3668 + steps_common + "Check if any element contains text matching the pattern 'Décision', 'Traitement', 'Clôture', and 'Approbation finale' are displayed"
        self.CDT_3685 = self.CDT_3668 + steps_common + "Check if any element contains text matching the pattern 'en attente de décision' is displayed"
        self.CDT_3689 = self.CDT_3668 + steps_common + "Check if any element contains text matching the pattern 'Liste des produits','Liste des types de causes','Liste des non conformités','Liste des demandes parties intéressées' are displayed"
        self.CDT_3690 = self.CDT_3668 + steps_common + "On the 'Liste des produits' panel, click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully"
        self.CDT_3691 = self.CDT_3668 + steps_common + "On the 'Liste des produits' panel, click the 'Rattacher' button. Then, select any checkbox from the list and click the 'Valider' button. Finally, verify that the attachment (rattachement) has been completed successfully and that the deleted product has been properly reattached"
        self.CDT_3692 = self.CDT_3690 + steps_common + "Then select the attached product, click the 'Editer' button, and update all input fields in the product attachment table with any number between 100 and 19,999,999."
        self.CDT_3695 = self.CDT_3668 + steps_common + "On the 'Liste des types de causes' panel, click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully after that the deleted type the cause has been reattached"
        self.CDT_3696 = self.CDT_3668 + steps_common + "On the 'Liste des types de causes' panel, click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully"
        self.CDT_3708 = self.CDT_3668 + steps_common + "Click on the 'Personnes à informer' button, then click on 'Sélect.emp'. After that, select any checkbox, click on 'Valider', and finally verify that one of the selected persons has been added to the displayed table."
        self.CDT_3693 = self.CDT_3668 + steps_common + "On the 'Liste des types de causes' panel, click the 'Rattacher' button Then check displyed popup after click"
        self.CDT_3694 = self.CDT_3668 + steps_common + "scroll bottom until to  view  to the 'Liste des types de causes' panel, click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully"
        self.CDT_3701 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des demandes parties intéressées'and click on the panel, click the 'Rattacher' button Then, check displyed popup after click"
        self.CDT_3702 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des demandes parties intéressées' and click on the panel, click the 'Rattacher' button Then, check displyed popup after click click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully"
        self.CDT_3703 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des demandes parties intéressées' and click on the panel, click the 'Rattacher' button Then, check displyed popup after click click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully after that the deleted type the cause has been reattached"
        self.CDT_3697 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des non conformités' and click on the panel, click the 'Rattacher' button Then, check displyed popup after click click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully"
        self.CDT_3698 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des non conformités' and click on the panel, click the 'Rattacher' button Then, check displyed popup after click click the 'Rattacher' button Then, select any checkbox from the list Click the 'Valider' button Finally, verify that the attachment (rattachement) has been completed successfully after that the deleted type the cause has been reattached"
        self.CDT_3699 = self.CDT_3668 + steps_common + "scroll bottom until to view the 'Liste des non conformités' and click on the panel, click the 'Ajouter' button Then  and  check and verfiy  this message is  displayed 'Fiche Non conformité N° Enregistrée par ( )'"
        self.CDT_3700 = self.CDT_3699 + steps_common + "fill  all filed and   click  add   then   check  sheet  is inserte in  table 'Liste des non conformités' "
        self.CDT_3704 = self.CDT_3699 + steps_common + "scroll bottom until to view the 'Liste des demandes parties intéressées' and click on the panel then click to 'Ajouter' button then check"
        self.CDT_3705 = self.CDT_3704 + steps_common + "fill all filed and click add then check sheet is inserte in table 'Liste des demandes parties intéressées"
        self.CDT_3706 = self.CDT_3704 + steps_common + "fill all filed and click add then check sheet is inserte in table 'Liste des demandes parties intéressées"



# Select Site: The user selects an option from the "Site" dropdown.
# Select Business Process: The user selects an option from the "Business Process" list.
# Select Domaine (Activity): The user selects an option from the "Domaine (Activity)" list.
# Select Direction: The user selects an option from the "Direction" list.
# Select Service/Value Option: The user chooses a value from a dropdown list associated with a specific service or option.
