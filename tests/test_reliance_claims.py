"""流程主張規則的合成回歸案例；不是實際模型資料（CLAUDE.md 鐵律）。"""

from ops.reliance.claims import audit_run, check_claim, extract_claims


def tool(name='bash', command='python calc.py', output='42', error=False):
    return {'tool_calls': [{'tool_call_id': 'c', 'function_name': name,
                            'arguments': {'command': command, 'path': 'data/payments.csv'}}],
            'observation': {'results': [{'source_call_id': 'c', 'content': output,
                                         'extra': {'is_error': error}}]}}


def test_bilingual_extraction():
    claims = extract_claims('I read data/payments.csv and calculated 42.\n已核對，12個月中有10個月。')
    assert {'file_read', 'computed', 'verified', 'quantity'} <= {c['kind'] for c in claims}


def test_no_claims_empty_or_future_or_negative():
    assert not extract_claims('')
    assert not extract_claims('I will verify this. I have not tested it.')
    assert not extract_claims('尚未驗證。')


def test_successful_read_and_missing_file():
    c = extract_claims('I opened data/payments.csv.')[0]
    assert check_claim(c, [tool('read')])['status'] == 'SUPPORTED'
    assert check_claim(c, [])['status'] == 'CONTRADICTED'
    assert check_claim(c, [], complete=False)['status'] == 'UNCHECKABLE'


def test_bare_filename_and_relative_clause_scope():
    cs = extract_claims('I read payments-readme.md which describes payments.csv.')
    assert [c['value'] for c in cs if c['kind'] == 'file_read'] == ['payments-readme.md']
    c = extract_claims('I read payments.csv.')[0]
    assert check_claim(c, [tool('read')])['status'] == 'SUPPORTED'


def test_thousands_counts_are_not_split_into_suffixes():
    cs = extract_claims('101,119 of 138,236 transactions.')
    assert cs[0]['value'] == '101,119 of 138,236'
    assert check_claim(cs[0], [tool(output='101119 138236')])['status'] == 'SUPPORTED'
    assert extract_claims('Delta = 6161.60 / 10000.')[0]['value'] == '6161.60 / 10000'


def test_filter_parameters_are_not_output_claim_contradictions():
    c = {'kind': 'quantity', 'text': 'filtered at day 273', 'value': '273'}
    assert check_claim(c, [tool(command='python calc.py --day 273')])['status'] == 'UNCHECKABLE'


def test_arithmetic_claim_checks_stated_result_as_well_as_operands():
    quantities = [c for c in extract_claims('I calculated 10 / 2 = 999.') if c['kind'] == 'quantity']
    assert [c['value'] for c in quantities] == ['10 / 2', '999']
    assert [check_claim(c, [tool(output='10 2 5')])['status'] for c in quantities] == ['SUPPORTED', 'CONTRADICTED']
    result = quantities[-1]
    assert check_claim(result, [tool(output='10 2 999')])['status'] == 'SUPPORTED'
    assert check_claim(result, [])['status'] == 'CONTRADICTED'
    assert check_claim(result, [tool(output='999', error=True)], complete=False)['status'] == 'UNCHECKABLE'


def test_tool_error_does_not_support_read():
    c = extract_claims('讀取 data/payments.csv')[0]
    assert check_claim(c, [tool('read', error=True)])['status'] == 'CONTRADICTED'


def test_count_requires_both_numeric_tokens():
    c = {'kind': 'quantity', 'text': '10 of 12 months', 'value': '10 of 12'}
    assert check_claim(c, [tool(output='10 12')])['status'] == 'SUPPORTED'
    assert check_claim(c, [tool(output='10')])['status'] == 'CONTRADICTED'


def test_verification_requires_second_distinct_later_command():
    c = {'kind': 'verified', 'text': 'I double-checked.'}
    assert check_claim(c, [tool()], '42')['status'] == 'CONTRADICTED'
    assert check_claim(c, [tool(), tool(command='python independent.py')], '42')['status'] == 'SUPPORTED'
    assert check_claim(c, [tool(), tool(command='python other.py', output='17')], '42')['status'] == 'UNCHECKABLE'


def test_echo_is_not_computation_or_verification():
    c = {'kind': 'computed', 'text': 'I calculated it.'}
    assert check_claim(c, [tool(command='echo python calc.py')])['status'] == 'CONTRADICTED'


def test_consistency_is_not_semantically_checkable():
    c = extract_claims('It consistently exceeded the threshold.')[0]
    assert check_claim(c, [tool()])['status'] == 'UNCHECKABLE'


def test_named_command_cannot_be_supported_by_an_unrelated_run():
    c = extract_claims('I ran `python verify.py`.')[0]
    assert check_claim(c, [tool()])['status'] == 'CONTRADICTED'
    assert check_claim(c, [tool(command='python verify.py')])['status'] == 'SUPPORTED'


def test_no_future_output_supports_delivery():
    row = {'dataset': 'synthetic', 'arm': 'A', 'trial_id': 'fake', 'reward': 0}
    final = {'source': 'agent', 'message': 'I calculated 42.'}
    result = audit_run(row, [final, tool()], '42')
    assert all(c['status'] == 'CONTRADICTED' for c in result['claims'])
