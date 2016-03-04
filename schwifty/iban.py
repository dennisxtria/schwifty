from functools import partial
import re
import string

from schwifty.bic import BIC
from schwifty.common import Base
from schwifty import registry


_spec_to_re = {
    'n': r'\d',
    'a': r'[A-Z]',
    'c': r'[A-Za-z0-9]',
    'e': r' '
}

_alphabet = string.digits + string.ascii_uppercase


def _get_iban_spec(country_code):
    try:
        return registry.get('iban')[country_code]
    except KeyError:
        raise ValueError('Unknown country-code %s' % country_code)


def numerify(string):
    return int(''.join(str(_alphabet.index(c)) for c in string))


def code_length(spec, code_type):
    start, end = spec['positions'][code_type]
    return end - start


class IBAN(Base):

    def __init__(self, iban, allow_invalid=False):
        super(IBAN, self).__init__(iban)
        self._parse(iban)
        if not allow_invalid:
            self.validate()

    def _parse(self, iban):
        if self.checksum_digits == '??':
            self._code = self.country_code + self._calc_checksum_digits() + self.bban

    def _calc_checksum_digits(self):
        return '{:2d}'.format(98 - (numerify(self.bban + self.country_code) * 100) % 97)

    @classmethod
    def generate(cls, country_code, bank_code, account_code):
        spec = _get_iban_spec(country_code)
        bank_code_length = code_length(spec, 'bank_code')
        branch_code_length = code_length(spec, 'branch_code')
        bank_and_branch_code_length = bank_code_length + branch_code_length
        account_code_length = code_length(spec, 'account_code')

        if len(bank_code) > bank_and_branch_code_length:
            raise ValueError('Bank code exceeds maximum size %d' % bank_and_branch_code_length)

        if len(account_code) > account_code_length:
            raise ValueError('Account code exceeds maximum size %d' % account_code_length)

        bank_code = bank_code.rjust(bank_and_branch_code_length, '0')
        account_code = account_code.rjust(account_code_length, '0')
        iban = country_code + '??' + bank_code + account_code
        return cls(iban)

    def validate(self):
        self.validate_characters()
        self.validate_length()
        self.validate_format()
        self.validate_checksum()
        return True

    def validate_characters(self):
        if not re.match(r'[A-Z]{2}\d{2}[A-Z]*', self.compact):
            raise ValueError('Invalid characters in IBAN')

    def validate_checksum(self):
        if self.numeric % 97 != 1:
            raise ValueError('Invalid checksum digits')

    def validate_length(self):
        if self.spec['iban_length'] != self.length:
            raise ValueError('Invalid IBAN length')

    def validate_format(self):
        if not self.spec['regex'].match(self.bban):
            raise ValueError('Invalid BBAN structure: \'%s\' doesn\'t match %s' %
                             (self.bban, self.spec['bban_spec']))

    @property
    def numeric(self):
        return numerify(self.bban + self.compact[:4])

    @property
    def formatted(self):
        return ' '.join(self.compact[i:i + 4] for i in range(0, len(self.compact), 4))

    @property
    def spec(self):
        return _get_iban_spec(self.country_code)

    @property
    def bic(self):
        return BIC.from_bank_code(self.country_code, self.bank_code)

    def _get_code(self, code_type):
        start, end = self.spec['positions'][code_type]
        return self.bban[start:end]

    bban = property(partial(Base._get_component, start=4))
    country_code = property(partial(Base._get_component, start=0, end=2))
    checksum_digits = property(partial(Base._get_component, start=2, end=4))
    bank_code = property(partial(_get_code, code_type='bank_code'))
    branch_code = property(partial(_get_code, code_type='branch_code'))
    account_code = property(partial(_get_code, code_type='account_code'))


def add_bban_regex(country, spec):
    bban_spec = spec['bban_spec']
    spec_re = r'(\d+)(!)?([{}])'.format(''.join(_spec_to_re.keys()))

    def convert(match):
        quantifier = ('{%s}' if match.group(2) else '{1,%s}') % match.group(1)
        return _spec_to_re[match.group(3)] + quantifier
    spec['regex'] = re.compile('^%s$' % re.sub(spec_re, convert, bban_spec))
    return spec

registry.manipulate('iban', add_bban_regex)