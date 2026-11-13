import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_km.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'l10n/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
    : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations? of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations);
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
        delegate,
        GlobalMaterialLocalizations.delegate,
        GlobalCupertinoLocalizations.delegate,
        GlobalWidgetsLocalizations.delegate,
      ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('km'),
  ];

  /// No description provided for @appTitle.
  ///
  /// In en, this message translates to:
  /// **'LCS Finance'**
  String get appTitle;

  /// No description provided for @dashboard.
  ///
  /// In en, this message translates to:
  /// **'Dashboard'**
  String get dashboard;

  /// No description provided for @finance.
  ///
  /// In en, this message translates to:
  /// **'Finance'**
  String get finance;

  /// No description provided for @accounting.
  ///
  /// In en, this message translates to:
  /// **'Accounting'**
  String get accounting;

  /// No description provided for @reports.
  ///
  /// In en, this message translates to:
  /// **'Reports'**
  String get reports;

  /// No description provided for @login.
  ///
  /// In en, this message translates to:
  /// **'Login'**
  String get login;

  /// No description provided for @emailOrUsername.
  ///
  /// In en, this message translates to:
  /// **'Email or username'**
  String get emailOrUsername;

  /// No description provided for @password.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get password;

  /// No description provided for @rememberMe.
  ///
  /// In en, this message translates to:
  /// **'Remember me'**
  String get rememberMe;

  /// No description provided for @signIn.
  ///
  /// In en, this message translates to:
  /// **'Sign in'**
  String get signIn;

  /// No description provided for @logout.
  ///
  /// In en, this message translates to:
  /// **'Log out'**
  String get logout;

  /// No description provided for @totalReceivables.
  ///
  /// In en, this message translates to:
  /// **'Total Receivables'**
  String get totalReceivables;

  /// No description provided for @totalPayables.
  ///
  /// In en, this message translates to:
  /// **'Total Payables'**
  String get totalPayables;

  /// No description provided for @totalReceived.
  ///
  /// In en, this message translates to:
  /// **'Total Received'**
  String get totalReceived;

  /// No description provided for @totalPaid.
  ///
  /// In en, this message translates to:
  /// **'Total Paid'**
  String get totalPaid;

  /// No description provided for @cashAndBank.
  ///
  /// In en, this message translates to:
  /// **'Cash & Bank'**
  String get cashAndBank;

  /// No description provided for @lastUpdated.
  ///
  /// In en, this message translates to:
  /// **'Last updated {time}'**
  String lastUpdated(String time);

  /// No description provided for @pullToRefresh.
  ///
  /// In en, this message translates to:
  /// **'Pull to refresh'**
  String get pullToRefresh;

  /// No description provided for @retry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get retry;

  /// No description provided for @search.
  ///
  /// In en, this message translates to:
  /// **'Search'**
  String get search;

  /// No description provided for @filters.
  ///
  /// In en, this message translates to:
  /// **'Filters'**
  String get filters;

  /// No description provided for @status.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get status;

  /// No description provided for @all.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get all;

  /// No description provided for @from.
  ///
  /// In en, this message translates to:
  /// **'From'**
  String get from;

  /// No description provided for @to.
  ///
  /// In en, this message translates to:
  /// **'To'**
  String get to;

  /// No description provided for @apply.
  ///
  /// In en, this message translates to:
  /// **'Apply'**
  String get apply;

  /// No description provided for @clear.
  ///
  /// In en, this message translates to:
  /// **'Clear'**
  String get clear;

  /// No description provided for @noResults.
  ///
  /// In en, this message translates to:
  /// **'No records found'**
  String get noResults;

  /// No description provided for @loadMore.
  ///
  /// In en, this message translates to:
  /// **'Load more'**
  String get loadMore;

  /// No description provided for @accountsReceivable.
  ///
  /// In en, this message translates to:
  /// **'Accounts Receivable'**
  String get accountsReceivable;

  /// No description provided for @accountsPayable.
  ///
  /// In en, this message translates to:
  /// **'Accounts Payable'**
  String get accountsPayable;

  /// No description provided for @customerReceipts.
  ///
  /// In en, this message translates to:
  /// **'Customer Receipts'**
  String get customerReceipts;

  /// No description provided for @supplierPayments.
  ///
  /// In en, this message translates to:
  /// **'Supplier Payments'**
  String get supplierPayments;

  /// No description provided for @customerInvoices.
  ///
  /// In en, this message translates to:
  /// **'Customer Invoices'**
  String get customerInvoices;

  /// No description provided for @supplierBills.
  ///
  /// In en, this message translates to:
  /// **'Supplier Bills'**
  String get supplierBills;

  /// No description provided for @creditNotes.
  ///
  /// In en, this message translates to:
  /// **'Credit Notes'**
  String get creditNotes;

  /// No description provided for @otherTransactions.
  ///
  /// In en, this message translates to:
  /// **'Other Transactions'**
  String get otherTransactions;

  /// No description provided for @documents.
  ///
  /// In en, this message translates to:
  /// **'Documents'**
  String get documents;

  /// No description provided for @serviceCharges.
  ///
  /// In en, this message translates to:
  /// **'Service Charges'**
  String get serviceCharges;

  /// No description provided for @journals.
  ///
  /// In en, this message translates to:
  /// **'Journal Vouchers'**
  String get journals;

  /// No description provided for @arReport.
  ///
  /// In en, this message translates to:
  /// **'Receivables Report'**
  String get arReport;

  /// No description provided for @apReport.
  ///
  /// In en, this message translates to:
  /// **'Payables Report'**
  String get apReport;

  /// No description provided for @trialBalance.
  ///
  /// In en, this message translates to:
  /// **'Trial Balance'**
  String get trialBalance;

  /// No description provided for @generalLedger.
  ///
  /// In en, this message translates to:
  /// **'General Ledger'**
  String get generalLedger;

  /// No description provided for @documentNo.
  ///
  /// In en, this message translates to:
  /// **'Document No.'**
  String get documentNo;

  /// No description provided for @date.
  ///
  /// In en, this message translates to:
  /// **'Date'**
  String get date;

  /// No description provided for @dueDate.
  ///
  /// In en, this message translates to:
  /// **'Due date'**
  String get dueDate;

  /// No description provided for @customer.
  ///
  /// In en, this message translates to:
  /// **'Customer'**
  String get customer;

  /// No description provided for @supplier.
  ///
  /// In en, this message translates to:
  /// **'Supplier'**
  String get supplier;

  /// No description provided for @amount.
  ///
  /// In en, this message translates to:
  /// **'Amount'**
  String get amount;

  /// No description provided for @total.
  ///
  /// In en, this message translates to:
  /// **'Total'**
  String get total;

  /// No description provided for @paidAmount.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get paidAmount;

  /// No description provided for @balance.
  ///
  /// In en, this message translates to:
  /// **'Balance'**
  String get balance;

  /// No description provided for @outstanding.
  ///
  /// In en, this message translates to:
  /// **'Outstanding'**
  String get outstanding;

  /// No description provided for @currency.
  ///
  /// In en, this message translates to:
  /// **'Currency'**
  String get currency;

  /// No description provided for @reference.
  ///
  /// In en, this message translates to:
  /// **'Reference'**
  String get reference;

  /// No description provided for @remark.
  ///
  /// In en, this message translates to:
  /// **'Remark'**
  String get remark;

  /// No description provided for @paymentMethod.
  ///
  /// In en, this message translates to:
  /// **'Payment method'**
  String get paymentMethod;

  /// No description provided for @financialAccount.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get financialAccount;

  /// No description provided for @createdBy.
  ///
  /// In en, this message translates to:
  /// **'Created by'**
  String get createdBy;

  /// No description provided for @createdAt.
  ///
  /// In en, this message translates to:
  /// **'Created at'**
  String get createdAt;

  /// No description provided for @lines.
  ///
  /// In en, this message translates to:
  /// **'Lines'**
  String get lines;

  /// No description provided for @allocations.
  ///
  /// In en, this message translates to:
  /// **'Payment allocations'**
  String get allocations;

  /// No description provided for @journal.
  ///
  /// In en, this message translates to:
  /// **'Journal'**
  String get journal;

  /// No description provided for @post.
  ///
  /// In en, this message translates to:
  /// **'Post'**
  String get post;

  /// No description provided for @reverse.
  ///
  /// In en, this message translates to:
  /// **'Reverse'**
  String get reverse;

  /// No description provided for @edit.
  ///
  /// In en, this message translates to:
  /// **'Edit'**
  String get edit;

  /// No description provided for @print.
  ///
  /// In en, this message translates to:
  /// **'Print / Preview'**
  String get print;

  /// No description provided for @download.
  ///
  /// In en, this message translates to:
  /// **'Download'**
  String get download;

  /// No description provided for @share.
  ///
  /// In en, this message translates to:
  /// **'Share'**
  String get share;

  /// No description provided for @confirmPost.
  ///
  /// In en, this message translates to:
  /// **'Post this document?'**
  String get confirmPost;

  /// No description provided for @postHint.
  ///
  /// In en, this message translates to:
  /// **'Posting creates an immutable accounting journal entry.'**
  String get postHint;

  /// No description provided for @confirmReverse.
  ///
  /// In en, this message translates to:
  /// **'Reverse this document?'**
  String get confirmReverse;

  /// No description provided for @reason.
  ///
  /// In en, this message translates to:
  /// **'Reason'**
  String get reason;

  /// No description provided for @save.
  ///
  /// In en, this message translates to:
  /// **'Save'**
  String get save;

  /// No description provided for @cancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get cancel;

  /// No description provided for @required.
  ///
  /// In en, this message translates to:
  /// **'Required'**
  String get required;

  /// No description provided for @invalidAmount.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid amount greater than zero'**
  String get invalidAmount;

  /// No description provided for @invalidDate.
  ///
  /// In en, this message translates to:
  /// **'Enter a valid date'**
  String get invalidDate;

  /// No description provided for @newReceipt.
  ///
  /// In en, this message translates to:
  /// **'New receipt'**
  String get newReceipt;

  /// No description provided for @newPayment.
  ///
  /// In en, this message translates to:
  /// **'New payment'**
  String get newPayment;

  /// No description provided for @postingFailed.
  ///
  /// In en, this message translates to:
  /// **'Posting failed'**
  String get postingFailed;

  /// No description provided for @sessionExpired.
  ///
  /// In en, this message translates to:
  /// **'Session expired. Please sign in again.'**
  String get sessionExpired;

  /// No description provided for @noConnection.
  ///
  /// In en, this message translates to:
  /// **'No connection. Check your network and try again.'**
  String get noConnection;

  /// No description provided for @serverError.
  ///
  /// In en, this message translates to:
  /// **'The server could not process the request.'**
  String get serverError;

  /// No description provided for @permissionDenied.
  ///
  /// In en, this message translates to:
  /// **'You do not have permission for this action.'**
  String get permissionDenied;

  /// No description provided for @notFound.
  ///
  /// In en, this message translates to:
  /// **'Record not found.'**
  String get notFound;

  /// No description provided for @draft.
  ///
  /// In en, this message translates to:
  /// **'Draft'**
  String get draft;

  /// No description provided for @posted.
  ///
  /// In en, this message translates to:
  /// **'Posted'**
  String get posted;

  /// No description provided for @partial.
  ///
  /// In en, this message translates to:
  /// **'Partial'**
  String get partial;

  /// No description provided for @open.
  ///
  /// In en, this message translates to:
  /// **'Open'**
  String get open;

  /// No description provided for @paidStatus.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get paidStatus;

  /// No description provided for @reversed.
  ///
  /// In en, this message translates to:
  /// **'Reversed'**
  String get reversed;

  /// No description provided for @chargeNo.
  ///
  /// In en, this message translates to:
  /// **'Charge No.'**
  String get chargeNo;

  /// No description provided for @description.
  ///
  /// In en, this message translates to:
  /// **'Description'**
  String get description;

  /// No description provided for @grandTotal.
  ///
  /// In en, this message translates to:
  /// **'Grand total'**
  String get grandTotal;

  /// No description provided for @feeLines.
  ///
  /// In en, this message translates to:
  /// **'Fee lines'**
  String get feeLines;

  /// No description provided for @entryNo.
  ///
  /// In en, this message translates to:
  /// **'Entry No.'**
  String get entryNo;

  /// No description provided for @entryType.
  ///
  /// In en, this message translates to:
  /// **'Type'**
  String get entryType;

  /// No description provided for @account.
  ///
  /// In en, this message translates to:
  /// **'Account'**
  String get account;

  /// No description provided for @debit.
  ///
  /// In en, this message translates to:
  /// **'Debit'**
  String get debit;

  /// No description provided for @credit.
  ///
  /// In en, this message translates to:
  /// **'Credit'**
  String get credit;

  /// No description provided for @generate.
  ///
  /// In en, this message translates to:
  /// **'Generate'**
  String get generate;

  /// No description provided for @exportCsv.
  ///
  /// In en, this message translates to:
  /// **'Export CSV'**
  String get exportCsv;

  /// No description provided for @accountCode.
  ///
  /// In en, this message translates to:
  /// **'Account code'**
  String get accountCode;

  /// No description provided for @accountName.
  ///
  /// In en, this message translates to:
  /// **'Account name'**
  String get accountName;

  /// No description provided for @difference.
  ///
  /// In en, this message translates to:
  /// **'Difference'**
  String get difference;

  /// No description provided for @profile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get profile;

  /// No description provided for @mustChangePassword.
  ///
  /// In en, this message translates to:
  /// **'You must change your password in the web application.'**
  String get mustChangePassword;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'km'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'km':
      return AppLocalizationsKm();
  }

  throw FlutterError(
    'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
    'an issue with the localizations generation tool. Please file an issue '
    'on GitHub with a reproducible sample app and the gen-l10n configuration '
    'that was used.',
  );
}
