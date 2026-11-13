import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdf/pdf.dart';
import 'package:pdf/widgets.dart' as pw;
import 'package:printing/printing.dart';

import '../../../core/utils/format.dart';

/// Reusable document preview: builds a PDF locally from the reconciled
/// print-data the backend produces (`/financial-documents/{id}/print-data`).
///
/// No accounting totals are calculated here — every amount comes from the
/// backend's already-validated `model.totals`. The endpoint serves customer
/// invoices only; other document types have no backend print contract yet.
class DocumentPreviewScreen extends StatelessWidget {
  const DocumentPreviewScreen({super.key, required this.printData});

  final Map<String, dynamic> printData;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Document preview'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share_outlined),
            tooltip: 'Share',
            onPressed: () => _share(printData),
          ),
        ],
      ),
      body: PdfPreview(
        canChangeOrientation: false,
        canDebug: false,
        dynamicLayout: false,
        build: (format) => _buildPdf(printData),
        pdfFileName: _fileName(printData),
      ),
    );
  }

  static String _fileName(Map<String, dynamic> printData) {
    final model =
        (printData['model'] as Map?)?.cast<String, dynamic>() ?? const {};
    final document =
        (model['document'] as Map?)?.cast<String, dynamic>() ?? const {};
    final number = document['number'] as String? ?? 'document';
    return '$number.pdf';
  }

  static Future<void> _share(Map<String, dynamic> printData) async {
    final bytes = await _buildPdf(printData);
    await Printing.sharePdf(bytes: bytes, filename: _fileName(printData));
  }
}

Future<Uint8List> _buildPdf(Map<String, dynamic> printData) async {
  final model =
      (printData['model'] as Map?)?.cast<String, dynamic>() ?? const {};
  final document =
      (model['document'] as Map?)?.cast<String, dynamic>() ?? const {};
  final issuer = (model['issuer'] as Map?)?.cast<String, dynamic>() ?? const {};
  final party = (model['party'] as Map?)?.cast<String, dynamic>() ?? const {};
  final totals = (model['totals'] as Map?)?.cast<String, dynamic>() ?? const {};
  final lines = (model['lines'] as List?) ?? const [];
  final precision = (model['precision'] is num) ? model['precision'] as int : 2;
  final currency =
      totals['currency'] as String? ?? document['currency'] as String? ?? '';
  final watermark = model['watermark'] as String?;

  final pdf = pw.Document();
  pdf.addPage(
    pw.MultiPage(
      pageFormat: PdfPageFormat.a4,
      margin: const pw.EdgeInsets.all(36),
      build: (context) => [
        pw.Row(
          mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
          crossAxisAlignment: pw.CrossAxisAlignment.start,
          children: [
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.start,
              children: [
                pw.Text(
                  '${issuer['legalName'] ?? ''}',
                  style: pw.TextStyle(
                    fontSize: 14,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                if ((issuer['address'] ?? '').toString().isNotEmpty)
                  pw.Text(
                    '${issuer['address']}',
                    style: const pw.TextStyle(fontSize: 9),
                  ),
                if ((issuer['taxIdentifier'] ?? '').toString().isNotEmpty)
                  pw.Text(
                    'Tax ID: ${issuer['taxIdentifier']}',
                    style: const pw.TextStyle(fontSize: 9),
                  ),
              ],
            ),
            pw.Column(
              crossAxisAlignment: pw.CrossAxisAlignment.end,
              children: [
                pw.Text(
                  (document['documentType'] == 'CUSTOMER_INVOICE')
                      ? 'INVOICE'
                      : 'DOCUMENT',
                  style: pw.TextStyle(
                    fontSize: 16,
                    fontWeight: pw.FontWeight.bold,
                  ),
                ),
                pw.Text('No: ${document['number'] ?? ''}'),
                pw.Text(
                  'Date: ${formatDate(document['issueDate'] as String?)}',
                ),
                if ((document['dueDate'] ?? '').toString().isNotEmpty)
                  pw.Text('Due: ${formatDate(document['dueDate'] as String?)}'),
                pw.Text('Currency: $currency'),
              ],
            ),
          ],
        ),
        pw.Divider(),
        pw.Text(
          'Customer',
          style: pw.TextStyle(fontWeight: pw.FontWeight.bold, fontSize: 10),
        ),
        pw.Text(
          '${party['legalName'] ?? ''}',
          style: const pw.TextStyle(fontSize: 10),
        ),
        if ((party['address'] ?? '').toString().isNotEmpty)
          pw.Text(
            '${party['address']}',
            style: const pw.TextStyle(fontSize: 9),
          ),
        pw.SizedBox(height: 12),
        pw.TableHelper.fromTextArray(
          headerStyle: pw.TextStyle(
            fontWeight: pw.FontWeight.bold,
            fontSize: 9,
          ),
          cellStyle: const pw.TextStyle(fontSize: 9),
          headers: const [
            '#',
            'Description',
            'Qty',
            'Unit price',
            'Discount',
            'Tax',
            'Amount',
          ],
          data: [
            for (var i = 0; i < lines.length; i++)
              [
                '${i + 1}',
                '${(lines[i] as Map)['description'] ?? ''}',
                '${(lines[i] as Map)['quantity'] ?? ''}',
                formatMoney(
                  _num((lines[i] as Map)['unitPrice']),
                  currency: '',
                  decimals: precision,
                ),
                formatMoney(
                  _num((lines[i] as Map)['discount'] ?? 0),
                  currency: '',
                  decimals: precision,
                ),
                formatMoney(
                  _num((lines[i] as Map)['taxAmount'] ?? 0),
                  currency: '',
                  decimals: precision,
                ),
                formatMoney(
                  _num((lines[i] as Map)['amount'] ?? 0),
                  currency: '',
                  decimals: precision,
                ),
              ],
          ],
        ),
        pw.SizedBox(height: 12),
        pw.Container(
          alignment: pw.Alignment.centerRight,
          child: pw.Column(
            crossAxisAlignment: pw.CrossAxisAlignment.end,
            children: [
              _totalRow('Subtotal', totals['subtotal'], currency, precision),
              if (_num(totals['discount']) > 0)
                _totalRow('Discount', totals['discount'], currency, precision),
              if (_num(totals['taxAmount']) > 0)
                _totalRow(
                  'Tax (${totals['taxRate'] ?? 0}%)',
                  totals['taxAmount'],
                  currency,
                  precision,
                ),
              pw.Divider(),
              pw.Text(
                'Grand total: ${formatMoney(_num(totals['grandTotal']), currency: currency, decimals: precision)}',
                style: pw.TextStyle(
                  fontWeight: pw.FontWeight.bold,
                  fontSize: 12,
                ),
              ),
              pw.Text(
                'Outstanding: ${formatMoney(_num(totals['outstanding']), currency: currency, decimals: precision)}',
                style: const pw.TextStyle(fontSize: 10),
              ),
            ],
          ),
        ),
        if (watermark != null)
          pw.Align(
            alignment: pw.Alignment.center,
            child: pw.Text(
              watermark,
              style: pw.TextStyle(fontSize: 42, color: PdfColors.grey400),
            ),
          ),
      ],
    ),
  );
  return pdf.save();
}

pw.Widget _totalRow(
  String label,
  Object? value,
  String currency,
  int precision,
) {
  return pw.Padding(
    padding: const pw.EdgeInsets.symmetric(vertical: 1),
    child: pw.Row(
      mainAxisAlignment: pw.MainAxisAlignment.spaceBetween,
      children: [
        pw.Text('$currency $label', style: const pw.TextStyle(fontSize: 9)),
        pw.Text(
          formatMoney(_num(value), currency: '', decimals: precision),
          style: const pw.TextStyle(fontSize: 10),
        ),
      ],
    ),
  );
}

num _num(Object? value) =>
    value is num ? value : num.tryParse('${value ?? ''}') ?? 0;
