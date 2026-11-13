// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appTitle => 'LCS Finance';

  @override
  String get dashboard => 'Dashboard';

  @override
  String get finance => 'Finance';

  @override
  String get accounting => 'Accounting';

  @override
  String get reports => 'Reports';

  @override
  String get login => 'Login';

  @override
  String get emailOrUsername => 'Email or username';

  @override
  String get password => 'Password';

  @override
  String get rememberMe => 'Remember me';

  @override
  String get signIn => 'Sign in';

  @override
  String get logout => 'Log out';

  @override
  String get totalReceivables => 'Total Receivables';

  @override
  String get totalPayables => 'Total Payables';

  @override
  String get totalReceived => 'Total Received';

  @override
  String get totalPaid => 'Total Paid';

  @override
  String get cashAndBank => 'Cash & Bank';

  @override
  String lastUpdated(String time) {
    return 'Last updated $time';
  }

  @override
  String get pullToRefresh => 'Pull to refresh';

  @override
  String get retry => 'Retry';

  @override
  String get search => 'Search';

  @override
  String get filters => 'Filters';

  @override
  String get status => 'Status';

  @override
  String get all => 'All';

  @override
  String get from => 'From';

  @override
  String get to => 'To';

  @override
  String get apply => 'Apply';

  @override
  String get clear => 'Clear';

  @override
  String get noResults => 'No records found';

  @override
  String get loadMore => 'Load more';

  @override
  String get accountsReceivable => 'Accounts Receivable';

  @override
  String get accountsPayable => 'Accounts Payable';

  @override
  String get customerReceipts => 'Customer Receipts';

  @override
  String get supplierPayments => 'Supplier Payments';

  @override
  String get customerInvoices => 'Customer Invoices';

  @override
  String get supplierBills => 'Supplier Bills';

  @override
  String get creditNotes => 'Credit Notes';

  @override
  String get otherTransactions => 'Other Transactions';

  @override
  String get documents => 'Documents';

  @override
  String get serviceCharges => 'Service Charges';

  @override
  String get journals => 'Journal Vouchers';

  @override
  String get arReport => 'Receivables Report';

  @override
  String get apReport => 'Payables Report';

  @override
  String get trialBalance => 'Trial Balance';

  @override
  String get generalLedger => 'General Ledger';

  @override
  String get documentNo => 'Document No.';

  @override
  String get date => 'Date';

  @override
  String get dueDate => 'Due date';

  @override
  String get customer => 'Customer';

  @override
  String get supplier => 'Supplier';

  @override
  String get amount => 'Amount';

  @override
  String get total => 'Total';

  @override
  String get paidAmount => 'Paid';

  @override
  String get balance => 'Balance';

  @override
  String get outstanding => 'Outstanding';

  @override
  String get currency => 'Currency';

  @override
  String get reference => 'Reference';

  @override
  String get remark => 'Remark';

  @override
  String get paymentMethod => 'Payment method';

  @override
  String get financialAccount => 'Account';

  @override
  String get createdBy => 'Created by';

  @override
  String get createdAt => 'Created at';

  @override
  String get lines => 'Lines';

  @override
  String get allocations => 'Payment allocations';

  @override
  String get journal => 'Journal';

  @override
  String get post => 'Post';

  @override
  String get reverse => 'Reverse';

  @override
  String get edit => 'Edit';

  @override
  String get print => 'Print / Preview';

  @override
  String get download => 'Download';

  @override
  String get share => 'Share';

  @override
  String get confirmPost => 'Post this document?';

  @override
  String get postHint =>
      'Posting creates an immutable accounting journal entry.';

  @override
  String get confirmReverse => 'Reverse this document?';

  @override
  String get reason => 'Reason';

  @override
  String get save => 'Save';

  @override
  String get cancel => 'Cancel';

  @override
  String get required => 'Required';

  @override
  String get invalidAmount => 'Enter a valid amount greater than zero';

  @override
  String get invalidDate => 'Enter a valid date';

  @override
  String get newReceipt => 'New receipt';

  @override
  String get newPayment => 'New payment';

  @override
  String get postingFailed => 'Posting failed';

  @override
  String get sessionExpired => 'Session expired. Please sign in again.';

  @override
  String get noConnection => 'No connection. Check your network and try again.';

  @override
  String get serverError => 'The server could not process the request.';

  @override
  String get permissionDenied => 'You do not have permission for this action.';

  @override
  String get notFound => 'Record not found.';

  @override
  String get draft => 'Draft';

  @override
  String get posted => 'Posted';

  @override
  String get partial => 'Partial';

  @override
  String get open => 'Open';

  @override
  String get paidStatus => 'Paid';

  @override
  String get reversed => 'Reversed';

  @override
  String get chargeNo => 'Charge No.';

  @override
  String get description => 'Description';

  @override
  String get grandTotal => 'Grand total';

  @override
  String get feeLines => 'Fee lines';

  @override
  String get entryNo => 'Entry No.';

  @override
  String get entryType => 'Type';

  @override
  String get account => 'Account';

  @override
  String get debit => 'Debit';

  @override
  String get credit => 'Credit';

  @override
  String get generate => 'Generate';

  @override
  String get exportCsv => 'Export CSV';

  @override
  String get accountCode => 'Account code';

  @override
  String get accountName => 'Account name';

  @override
  String get difference => 'Difference';

  @override
  String get profile => 'Profile';

  @override
  String get mustChangePassword =>
      'You must change your password in the web application.';
}
