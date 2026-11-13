import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/api/api_exception.dart';
import '../../../core/widgets/common.dart';
import '../data/document_models.dart';
import '../data/document_repository.dart';

/// Create/edit arguments: a fixed document type (receipt/payment/other) and,
/// when editing, the draft document itself.
class DocumentFormArgs {
  const DocumentFormArgs({required this.documentType, this.existing});

  final String documentType;
  final FinancialDocument? existing;
}

/// Draft receipt/payment/other-entry form matching `DOCUMENT_WRITE_SCHEMA` +
/// a single line, exactly as the web form posts it.
class DocumentFormScreen extends ConsumerStatefulWidget {
  const DocumentFormScreen({super.key, required this.args});

  final DocumentFormArgs args;

  @override
  ConsumerState<DocumentFormScreen> createState() => _DocumentFormScreenState();
}

class _DocumentFormScreenState extends ConsumerState<DocumentFormScreen> {
  final _formKey = GlobalKey<FormState>();
  final _amountController = TextEditingController();
  final _descriptionController = TextEditingController();
  final _referenceController = TextEditingController();
  final _remarkController = TextEditingController();

  String? _partyId;
  String? _partyName;
  String? _accountId;
  String? _accountName;
  DateTime _documentDate = DateTime.now();
  DateTime? _valueDate;
  bool _submitting = false;

  DocumentFormArgs get _args => widget.args;

  bool get _isPayment =>
      _args.documentType == 'CUSTOMER_RECEIPT' ||
      _args.documentType == 'SUPPLIER_PAYMENT';

  @override
  void initState() {
    super.initState();
    final existing = widget.args.existing;
    if (existing != null) {
      _amountController.text = existing.total == 0
          ? ''
          : existing.total.toString();
      _descriptionController.text = existing.lines.isNotEmpty
          ? existing.lines.first.description
          : '';
      _referenceController.text = existing.referenceNumber ?? '';
      _remarkController.text = existing.remark ?? '';
      _partyId = existing.raw['partyId']?.toString();
      _partyName = existing.customer;
      _accountId = existing.financialAccountId;
      _accountName = existing.financialAccount;
      final date = DateTime.tryParse(existing.documentDate ?? '');
      if (date != null) _documentDate = date;
      final valueDate = DateTime.tryParse(
        existing.raw['valueDate']?.toString() ?? '',
      );
      if (valueDate != null) _valueDate = valueDate;
    }
  }

  @override
  void dispose() {
    _amountController.dispose();
    _descriptionController.dispose();
    _referenceController.dispose();
    _remarkController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!_formKey.currentState!.validate()) return;
    final amount = num.tryParse(_amountController.text.replaceAll(',', ''));
    if (amount == null || amount <= 0) {
      _showError('Enter a valid amount greater than zero');
      return;
    }
    setState(() => _submitting = true);
    final repo = ref.read(documentRepositoryProvider);
    final existing = _args.existing;
    final payload = {
      if (existing != null) 'id': existing.id,
      'documentType': _args.documentType,
      'documentDate': _documentDate.toIso8601String().substring(0, 10),
      if (_isPayment && _valueDate != null)
        'valueDate': _valueDate!.toIso8601String().substring(0, 10),
      if (_partyId != null) 'partyId': _partyId,
      if (_accountId != null) 'financialAccountId': _accountId,
      if (_referenceController.text.trim().isNotEmpty)
        'referenceNumber': _referenceController.text.trim(),
      if (_remarkController.text.trim().isNotEmpty)
        'remark': _remarkController.text.trim(),
      'lines': [
        {
          'description': _descriptionController.text.trim().isEmpty
              ? 'Payment'
              : _descriptionController.text.trim(),
          'quantity': 1,
          'unitPrice': amount,
        },
      ],
    };
    try {
      await repo.save(payload, id: existing?.id);
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(const SnackBar(content: Text('Draft saved.')));
        Navigator.of(context).pop(true);
      }
    } on ApiException catch (error) {
      if (mounted) {
        if (error.fieldErrors.isNotEmpty) {
          _showError(error.fieldErrors.values.first);
        } else {
          _showError(messageForError(error));
        }
      }
    } finally {
      if (mounted) setState(() => _submitting = false);
    }
  }

  void _showError(String message) {
    ScaffoldMessenger.of(
      context,
    ).showSnackBar(SnackBar(content: Text(message)));
  }

  @override
  Widget build(BuildContext context) {
    final existing = _args.existing;
    final title = existing != null
        ? 'Edit ${existing.documentNo}'
        : (_isPayment
              ? (_args.documentType == 'CUSTOMER_RECEIPT'
                    ? 'New receipt'
                    : 'New payment')
              : 'New document');

    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: AbsorbPointer(
        absorbing: _submitting,
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _PartyField(
                initialId: _partyId,
                initialName: _partyName,
                onSelected: (id, name) {
                  setState(() {
                    _partyId = id;
                    _partyName = name;
                  });
                },
              ),
              if (_isPayment) ...[
                const SizedBox(height: 12),
                _AccountField(
                  initialId: _accountId,
                  initialName: _accountName,
                  onSelected: (id, name) {
                    setState(() {
                      _accountId = id;
                      _accountName = name;
                    });
                  },
                ),
              ],
              const SizedBox(height: 12),
              TextFormField(
                controller: _amountController,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(labelText: 'Amount'),
                validator: (value) {
                  final amount = num.tryParse(
                    (value ?? '').replaceAll(',', ''),
                  );
                  if (amount == null || amount <= 0) {
                    return 'Enter a valid amount greater than zero';
                  }
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _descriptionController,
                decoration: const InputDecoration(labelText: 'Description'),
                maxLength: 1000,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _referenceController,
                decoration: const InputDecoration(labelText: 'Reference'),
                maxLength: 128,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: _remarkController,
                decoration: const InputDecoration(labelText: 'Remark'),
                maxLength: 10000,
              ),
              const SizedBox(height: 12),
              _DateField(
                label: 'Document date',
                initial: _documentDate,
                onChanged: (date) => _documentDate = date,
              ),
              if (_isPayment) ...[
                const SizedBox(height: 12),
                _DateField(
                  label: 'Value date',
                  initial: _valueDate,
                  onChanged: (date) => _valueDate = date,
                ),
              ],
              const SizedBox(height: 24),
              FilledButton(
                onPressed: _submitting ? null : _submit,
                child: Text(_submitting ? 'Saving…' : 'Save draft'),
              ),
              const SizedBox(height: 8),
              const Text(
                'The draft is posted from the detail screen; posting creates the '
                'accounting journal on the backend.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 12, color: Colors.grey),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PartyField extends ConsumerStatefulWidget {
  const _PartyField({
    required this.initialId,
    required this.initialName,
    required this.onSelected,
  });

  final String? initialId;
  final String? initialName;
  final void Function(String id, String name) onSelected;

  @override
  ConsumerState<_PartyField> createState() => _PartyFieldState();
}

class _PartyFieldState extends ConsumerState<_PartyField> {
  List<PartyOption>? _options;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(documentRepositoryProvider);
      final options = await repo.parties();
      if (mounted) setState(() => _options = options);
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(messageForError(error))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final options = _options;
    return DropdownButtonFormField<String>(
      initialValue: widget.initialId,
      isExpanded: true,
      decoration: InputDecoration(
        labelText:
            widget.initialName ??
            (options == null ? 'Loading parties…' : 'Business party'),
      ),
      items: options
          ?.map(
            (option) =>
                DropdownMenuItem(value: option.id, child: Text(option.name)),
          )
          .toList(),
      validator: (value) => value == null ? 'Select a business party' : null,
      onChanged: options == null
          ? null
          : (value) {
              final selected = options.firstWhere((o) => o.id == value);
              widget.onSelected(selected.id, selected.name);
            },
    );
  }
}

class _AccountField extends ConsumerStatefulWidget {
  const _AccountField({
    required this.initialId,
    required this.initialName,
    required this.onSelected,
  });

  final String? initialId;
  final String? initialName;
  final void Function(String id, String name) onSelected;

  @override
  ConsumerState<_AccountField> createState() => _AccountFieldState();
}

class _AccountFieldState extends ConsumerState<_AccountField> {
  List<FinancialAccountOption>? _options;

  @override
  void initState() {
    super.initState();
    Future<void>.microtask(_load);
  }

  Future<void> _load() async {
    try {
      final repo = ref.read(documentRepositoryProvider);
      final options = await repo.financialAccounts();
      if (mounted) setState(() => _options = options);
    } on ApiException catch (error) {
      if (mounted) {
        ScaffoldMessenger.of(
          context,
        ).showSnackBar(SnackBar(content: Text(messageForError(error))));
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final options = _options;
    return DropdownButtonFormField<String>(
      initialValue: widget.initialId,
      isExpanded: true,
      decoration: InputDecoration(
        labelText:
            widget.initialName ??
            (options == null ? 'Loading accounts…' : 'Financial account'),
      ),
      items: options
          ?.map(
            (option) => DropdownMenuItem(
              value: option.id,
              child: Text('${option.name} (${option.currency})'),
            ),
          )
          .toList(),
      onChanged: options == null
          ? null
          : (value) {
              final selected = options.firstWhere((o) => o.id == value);
              widget.onSelected(selected.id, selected.name);
            },
    );
  }
}

class _DateField extends StatelessWidget {
  const _DateField({
    required this.label,
    required this.initial,
    required this.onChanged,
  });

  final String label;
  final DateTime? initial;
  final void Function(DateTime) onChanged;

  @override
  Widget build(BuildContext context) {
    final value = initial;
    return InkWell(
      borderRadius: BorderRadius.circular(10),
      onTap: () async {
        final picked = await showDatePicker(
          context: context,
          initialDate: value ?? DateTime.now(),
          firstDate: DateTime(2000),
          lastDate: DateTime(2100),
        );
        if (picked != null) onChanged(picked);
      },
      child: InputDecorator(
        decoration: InputDecoration(
          labelText: label,
          suffixIcon: const Icon(Icons.calendar_today, size: 18),
        ),
        child: Text(
          value == null
              ? ''
              : '${value.year}-${value.month.toString().padLeft(2, '0')}-${value.day.toString().padLeft(2, '0')}',
        ),
      ),
    );
  }
}
