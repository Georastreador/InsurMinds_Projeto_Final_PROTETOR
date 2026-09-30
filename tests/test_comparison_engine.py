from decimal import Decimal
from schemas.policy import PolicySchema, Money, InsuringAgreement, InsuringSide, Coverage, Exclusion
from schemas.comparison import ComparisonStatus
from agents.comparison_agent import ComparisonAgent
from orchestration.comparison_pipeline import ComparisonPipeline
from orchestration.state import InsurMindsState, RunStatus
from storage.database import Database

def policies():
    a=PolicySchema(document_id='A',source_file='a.pdf',policy_number='1',insurer='Alpha',currency='BRL',limit_of_liability=Money(amount=Decimal('10000000'),currency='BRL'),insuring_agreements=[InsuringAgreement(side=InsuringSide.A,present=True)],coverages=[Coverage(name='Defense Costs',normalized_name='defense costs')],exclusions=[Exclusion(name='Pollution',normalized_name='pollution')])
    b=PolicySchema(document_id='B',source_file='b.pdf',policy_number='2',insurer='Beta',currency='BRL',limit_of_liability=Money(amount=Decimal('15000000'),currency='BRL'),insuring_agreements=[InsuringAgreement(side=InsuringSide.A,present=True),InsuringAgreement(side=InsuringSide.B,present=True)],coverages=[Coverage(name='Defense Costs',normalized_name='defense costs'),Coverage(name='Crisis',normalized_name='crisis')],exclusions=[])
    return a,b

def field(r,name): return next(x for x in r.fields if x.field==name)

def test_deterministic_money_difference():
    a,b=policies(); r=ComparisonAgent().compare('r',a,b); x=field(r,'limit_of_liability')
    assert x.status==ComparisonStatus.DIFFERENT and x.difference.absolute==5000000.0 and x.difference.percentage==50.0

def test_side_presence_only_b():
    a,b=policies(); r=ComparisonAgent().compare('r',a,b)
    assert field(r,'insuring_side_B').status==ComparisonStatus.ONLY_B

def test_semantic_lists_preserve_only_a_b():
    a,b=policies(); r=ComparisonAgent().compare('r',a,b)
    assert field(r,'coverages:crise_relacoes_publicas').status==ComparisonStatus.ONLY_B
    assert field(r,'exclusions:poluicao_ambiental').status==ComparisonStatus.ONLY_A

def test_equal_normalized_semantic_item():
    a,b=policies(); r=ComparisonAgent().compare('r',a,b)
    assert field(r,'coverages:custos_defesa').status==ComparisonStatus.EQUAL

def test_pipeline_persists_and_routes(tmp_path):
    a,b=policies(); s=InsurMindsState(run_id='run4',status=RunStatus.READY_TO_COMPARE,validated_policies=[a,b])
    dbp=tmp_path/'m4.db'; out=ComparisonPipeline(db_path=dbp).process(s)
    assert out.status==RunStatus.SYNTHESIZING and out.comparison is not None
    saved=Database(dbp).get_latest_comparison('run4')
    assert saved['policy_a_document_id']=='A' and saved['policy_b_document_id']=='B'

def test_requires_two_policies(tmp_path):
    a,_=policies(); s=InsurMindsState(run_id='run4',status=RunStatus.READY_TO_COMPARE,validated_policies=[a])
    try: ComparisonPipeline(db_path=tmp_path/'x.db').process(s); assert False
    except ValueError as e: assert 'two validated' in str(e)
