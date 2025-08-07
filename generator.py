import os
import io
import random
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_restful import Api, Resource
from flask_cors import CORS
from num2words import num2words
from pdfrw import PdfReader, PdfWriter, PdfDict, PdfObject, PdfString

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', '09d09ee1f301d1bed3877cbf7bb52e41726b53ef7c8ac75e0bb2df835b6a01ab').encode()
CORS(app)
api = Api(app)

# generates a random 6 digit number with current year and month
def generate_otp_with_date():
    otp = random.randint(100000, 999999)
    now = datetime.now()
    return f"{otp}/{now.strftime('%Y-%m')}"

class ReceiptGenerator(Resource):

    def post(self):
        try:
            data = request.get_json() # Get JSON data from the request body

            # Data unpacked from request dictionary
            payment = data['payment']
            vehicle = data['vehicle']
            client = data['client']

            pdf_bytes = self.generate_payment_pdf(payment, vehicle, client)

            # the send_file function sends the PDF file as a response to be viewed
            return send_file(
                io.BytesIO(pdf_bytes),
                download_name=f"Payment_{payment['id']}.pdf",
                mimetype='application/pdf',
                as_attachment=True # Downloads the file instead of displaying it in the browser
            )
        except Exception as e:
            return jsonify({'error': f'Failed to generate payment receipt: {str(e)}'}), 500

    # The generate PDF function   
    def generate_payment_pdf(self, payment, vehicle, client):
        template_path = "static/entry/RIFT-CARS-RECEIPT.pdf"
        template = PdfReader(template_path)

        # function to convert amount to words
        def amount_to_words(amount):
            shillings = int(amount)
            cents = int(round((amount - shillings) * 100))
            words = num2words(shillings, lang='en') + " Kenyan shillings"
            if cents:
                words += f" and {num2words(cents, lang='en')} cents"
            return words.upper()

        if payment['payment_method'] == 'mpesa':
            description = f"MPESA Paybill No {payment.get('mpesa_account_number', '')}"
        elif payment['payment_method'] == 'bank':
            description = f"Bank Account No {payment.get('bank_account_number', '')}"
        else:
            description = f"Payment for {vehicle['make']} {vehicle['model']}"

        field_values = {
            'PaymentID': generate_otp_with_date(),
            'TransactionNo': payment['transaction_number'],
            'Amount': f"{payment['amount']:.2f}",
            'AmountInWords': amount_to_words(payment['amount']),
            'PaymentMode': payment['payment_method'].capitalize(),
            'CarDesc': f"{vehicle['make']} {vehicle['model']}",
            'Description': description,
            'Authority': payment['authorized_by'],
            'ClientName': client['name'],
            'ClientID': client['id_number'],
            'CarReg': vehicle.get('registration_number', ''),
            'Date': payment['payment_date']
        }

        # Set NeedAppearances flag - Ensures field values are visible in PDF viewers
        if not template.Root.AcroForm:
            template.Root.AcroForm = PdfDict()
        template.Root.AcroForm.update(PdfDict(NeedAppearances=PdfObject('true')))

        for page in template.pages:
            annotations = page.Annots
            if annotations:
                for annot in annotations:
                    key = annot.T
                    if key:
                        field_name = key.to_unicode().strip()
                        if field_name in field_values:
                            value = field_values[field_name]
                            annot.update(
                                PdfDict(
                                    V=PdfString.encode(str(value)),
                                    Ff=1,  # Makes the file read-only
                                )
                            )

            # Writes and saves the modified PDF into memory.
            output_buffer = io.BytesIO()
            PdfWriter().write(output_buffer, template)
            output_buffer.seek(0)
            return output_buffer.read()
    
api.add_resource(ReceiptGenerator, '/receipts/payment')


if __name__ == "__main__":
    app.run(port=5900, debug=True)