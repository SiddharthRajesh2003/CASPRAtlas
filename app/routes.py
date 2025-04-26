from flask import Flask, render_template, redirect, flash, url_for, request
from app.db_connection import tables
from app.model_generator import Model_Generator
import os
from sqlalchemy import or_,func, extract
import requests
import logging
import random

tables = tables()
model_generator = Model_Generator(tables.models)
generated_models, session = model_generator.get_models()
app = Flask(__name__)
app.secret_key = os.getenv('secret_key')
app.logger.setLevel(logging.INFO)

@app.route('/')
def home():
    Paper = generated_models['paper']
    variants = generated_models['cas_variants']
    Dataset = generated_models['dataset']
    
    papers = Paper.query_all(session)
    cas_variants = variants.query_all(session)
    datasets = Dataset.query_all(session)
    
    
    joined=session.query(Dataset, Paper).join(Paper, Dataset.PM_ID==Paper.PUBMED_ID).all()
    enhanced=[]
    for data, paper in joined:
        enhanced.append({
            'DATA_ID': data.DATA_ID,
            'TITLE': paper.TITLE,
            'ORGANISM': data.ORGANISM,
            'DATASET_FILE': data.DATASET_FILE})
        
    featured_variants=random.sample(cas_variants, min(5, len(cas_variants)))
    featured_papers=random.sample(papers, min(5, len(papers)))
    featured_datasets=random.sample(enhanced, min(5, len(enhanced)))
    return render_template('home.html',is_home=True, papers=papers, cas_variants=cas_variants, datasets=datasets,
                           featured_papers=featured_papers, featured_datasets=featured_datasets, 
                           featured_variants=featured_variants)

@app.route('/cas_variants.html')
def cas_variants():
    try:
        Cas_variant = generated_models['cas_variants']
        cas_variants = Cas_variant.query_all(session)
        return render_template('cas_variants.html', cas_variants=cas_variants, is_home=False)
    except Exception as e:
        app.logger.error(f"Error in retrieving CAS variants: {e}")
        flash("Error in fetching CAS variants")
        return redirect(url_for('home'))

@app.route('/papers.html')
def papers():
    try:
        Paper = generated_models['paper']
        
        # Get the selected year from the query parameter
        selected_year = request.args.get('year', type=int)
        
        # If a year is selected, filter papers by that year
        if selected_year:
            papers = session.query(Paper).filter(extract('year', Paper.YEAR) == selected_year).all()
        else:
            papers = session.query(Paper).all()
        
        # Get distinct years for the dropdown
        distinct_years = session.query(func.extract('year', Paper.YEAR).label('year')).distinct().order_by('year').all()
        years = [int(year[0]) for year in distinct_years if year[0] is not None]
        
        return render_template('papers.html', 
                               papers=papers, 
                               is_home=False, 
                               years=years, 
                               selected_year=selected_year)
    
    except Exception as e:
        app.logger.error(f"Error in retrieving papers: {e}")
        flash("Error in fetching papers")
        return redirect(url_for('home'))

@app.route('/cas_protein.html')
def cas_protein():
    try:
        Cas_seq = generated_models['uniprot_fasta']
        variants = generated_models['cas_variants']
        structure = generated_models['cas_structure']
        complete = session.query(Cas_seq, variants, structure).join(variants, Cas_seq.UNIPROT_ID == variants.SEQ_ID).join(structure, Cas_seq.UNIPROT_ID == structure.UPROT_ID).all()
        enhanced = []
        for seqs, var, str in complete:
            enhanced.append({
                'UNIPROT_ID': seqs.UNIPROT_ID,
                'PDB_ID': str.PDB_AFOLD_ID,
                'Variant': var.UNIQUE_ID,
                'Protein': var.CAS_VARIANT,
                'Organism': seqs.ORGANISM,
                'FASTA_FILE': seqs.FASTA_FILE,
                'PDB_FILE': str.PDB_FILE
            })
        return render_template('cas_protein.html', cas_seqs=enhanced, is_home=False)
    except Exception as e:
        app.logger.error(f"Error in retrieving CAS protein data: {e}")
        flash("Error in fetching CAS protein data")
        return redirect(url_for('home'))

@app.route('/datasets.html')
def datasets():
    try:
        Dataset = generated_models['dataset']
        Paper = generated_models['paper']
        joined = session.query(Dataset, Paper).join(Paper, Dataset.PM_ID == Paper.PUBMED_ID).all()

        datasets = []
        for dataset, paper in joined:
            datasets.append({
                'DATA_ID': dataset.DATA_ID,
                'TITLE': paper.TITLE,
                'Variants': paper.CAS_PROTEIN,
                'PM_ID': dataset.PM_ID,
                'ORGANISM': dataset.ORGANISM,
                'DATASET_FILE': dataset.DATASET_FILE,
            })
        return render_template('datasets.html', datasets=datasets, is_home=False)
    
    except Exception as e:
        app.logger.error(f"Error in retrieving datasets: {e}")
        flash("Error in fetching datasets")
        return redirect(url_for('home'))

@app.route("/search.html")
def search():
    try:
        query = request.args.get('query')
        if not query:
            app.logger.error("No search query provided")
            flash("No search query provided")
            return render_template('search.html', results=None, is_home=False)
        
        results = {
            'cas_variants': [],
            'papers': [],
        }
        
        # CAS variants search
        Cas_variant = generated_models['cas_variants']
        cas_results = session.query(Cas_variant).filter(
            or_(*[getattr(Cas_variant, column).ilike(f'%{query}%')
                for column in Cas_variant.__table__.columns.keys()])
        ).all()
        results['cas_variants'] = cas_results

        # Get variant IDs that match the query for cross-referencing
        matching_variant_ids = [variant.UNIQUE_ID for variant in cas_results]
        
        # Papers search with direct query matching
        Paper = generated_models['paper']
        paper_results = session.query(Paper).filter(
            or_(*[getattr(Paper, column).ilike(f'%{query}%')
                for column in Paper.__table__.columns.keys()])
        ).all()
        
        # Additional search for papers referencing matching variants
        if matching_variant_ids:
            variant_papers = session.query(Paper).filter(
                Paper.CAS_PROTEIN.in_(matching_variant_ids)
            ).all()
            
            # Combine results, avoiding duplicates
            all_paper_ids = set(p.PUBMED_ID for p in paper_results)
            for paper in variant_papers:
                if paper.PUBMED_ID not in all_paper_ids:
                    paper_results.append(paper)
                    all_paper_ids.add(paper.PUBMED_ID)
        
        results['papers'] = paper_results
        
        return render_template('search.html', results=results, query=query, is_home=False)
    
    except Exception as e:
        query = request.args.get('query')
        app.logger.error(f"Error in retrieving search item {query}: {e}")
        flash("Error in search")
        return redirect(url_for('home'))

@app.route('/check_paper/<pm_id>')
def check_paper(pm_id):
    # Try PubMed first
    pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pm_id}/"
    try:
        pubmed_response = requests.get(pubmed_url)
        if pubmed_response.status_code == 200:
            return redirect(pubmed_url)
    except Exception as e:
        app.logger.error(f"Error accessing PubMed: {e}")
    
    # Then try DOI
    doi_url = f"https://doi.org/{pm_id}"
    try:
        doi_response = requests.get(doi_url)
        if doi_response.status_code == 200:
            return redirect(doi_url)
    except Exception as e:
        app.logger.error(f"Error accessing DOI: {e}")
    finally:
        app.logger.error(f"Paper not found in either PubMed or DOI: {pm_id}")
        flash("Paper not found in either PubMed or DOI")
        return redirect(url_for('datasets'))

@app.route('/uniprot/<uniprot_id>')
def show_uniprot(uniprot_id):
    uniprot_url=f'https://www.uniprot.org/uniprotkb/{uniprot_id}/entry'
    try:
        response = requests.get(uniprot_url)
        if response.status_code == 200:
            return redirect(uniprot_url)
    except Exception as e:
        app.logger.error('Cannot redirect to Uniprot')
        return redirect(url_for('cas_protein'))
    
@app.route('/pdb/<pdb_id>')
def show_pdb(pdb_id):
    pdb_url=f'https://www.rcsb.org/structure/{pdb_id}'
    try:
        response = requests.get(pdb_url)
        if response.status_code == 200:
            return redirect(pdb_url)
    except Exception as e:
        app.logger.error('Cannot redirect to PDB')
    
    
    pdb_id=pdb_id[3:]
    alpha_url=f'https://www.alphafold.ebi.ac.uk/entry/{pdb_id}'
    try:
        response = requests.get(alpha_url)
        if response.status_code == 200:
            return redirect(alpha_url)
    except Exception as e:
        app.logger.error('Cannot redirect to AlphaFold')
        return redirect(url_for('cas_protein'))
    
        

@app.route('/cas_variants/<variant_id>')
def show_variant_details(variant_id):
    try:
        if variant_id.endswith('.html'):
            # Map common route names to their functions
            route_map = {
                'papers.html': 'papers',
                'cas_variants.html': 'cas_variants',
                'datasets.html': 'datasets',
                'cas_protein.html': 'cas_protein',
                'search.html': 'search'
            }
            
            if variant_id in route_map:
                return redirect(url_for(route_map[variant_id]))
            else:
                flash(f"Page {variant_id} not found")
                return redirect(url_for('home'))
        
        Cas_variant = generated_models['cas_variants']
        datasets = generated_models['dataset']
        Paper = generated_models['paper']

        variant = session.query(Cas_variant).filter_by(UNIQUE_ID=variant_id).first()

        related_papers = session.query(Paper).filter_by(CAS_PROTEIN=variant_id).all()

        paper_ids = [paper.PUBMED_ID for paper in related_papers]
        related_datasets = (session.query(datasets,Paper).join(Paper,datasets.PM_ID == Paper.PUBMED_ID).filter(datasets.PM_ID.in_(paper_ids)).all())

        enhanced_datasets = []
        for dataset, paper in related_datasets:
            enhanced_datasets.append({
                'DATA_ID': dataset.DATA_ID,
                'TITLE': paper.TITLE,
                'PM_ID': dataset.PM_ID,
                'ORGANISM': dataset.ORGANISM,
                'DATASET_FILE': dataset.DATASET_FILE,
            })

        return render_template('variant_details.html', 
                            variant=variant, 
                            papers=related_papers,
                            datasets=enhanced_datasets)
    
    except Exception as e:
        app.logger.error(f"Error in show_variant_details: {e}")
        flash("Error in fetching variant details")
        return redirect(url_for('home'))
    
@app.route('/dataset/<data_id>')
def view_dataset(data_id):
    datasets = generated_models['dataset']
    Paper=generated_models['paper']
    
    dataset = session.query(datasets).filter(datasets.DATA_ID==data_id).first()
    
    if not dataset:
        flash(f"Dataset {data_id} not found")
        return redirect(url_for('datasets'))
    
    paper=session.query(Paper).filter(Paper.PUBMED_ID==dataset.PM_ID).first()
    
    return render_template('view_dataset.html', dataset=dataset, paper=paper, title=f'Dataset {data_id}')