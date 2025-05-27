"""Implements the Wiseloculus API Queries."""

import logging
import aiohttp
import asyncio
from typing import Optional, List, Tuple, Any 
from datetime import datetime

import pandas as pd

from .lapis import Lapis


class WiseLoculusLapis(Lapis):
    """Wise-Loculus Instance API"""

    async def fetch_sample_aggregated(
            self,
            session: aiohttp.ClientSession, 
            mutation: str, 
            mutation_type: str, 
            date_range: Tuple[datetime, datetime], 
            location_name: Optional[str] = None
            ) -> dict[str, Any]:
        """
        Fetches aggregated sample data for a given mutation, type, date range, and optional location.
        """
        payload: dict[str, Any] = { 
            "sampling_dateFrom": date_range[0].strftime('%Y-%m-%d'),
            "sampling_dateTo": date_range[1].strftime('%Y-%m-%d'),
            "fields": ["sampling_date"]  
        }

        if mutation_type == "aminoAcid":
            payload["aminoAcidMutations"] = [mutation]
        elif mutation_type == "nucleotide":
            payload["nucleotideMutations"] = [mutation]
        else:
            logging.error(f"Unknown mutation type: {mutation_type}")
            return {"mutation": mutation, "data": None, "error": "Unknown mutation type"}

        if location_name:
            payload["location_name"] = location_name  

        logging.debug(f"Fetching sample aggregated with payload: {payload}")
        async with session.post(
            f'{self.server_ip}/sample/aggregated',
            headers={
                'accept': 'application/json',
                'Content-Type': 'application/json'
            },
            json=payload
        ) as response:
            if response.status == 200:
                data = await response.json()
                return {"mutation": mutation, "data": data.get('data', [])}
            else:
                logging.error(f"Failed to fetch data for mutation {mutation} (type: {mutation_type}, location: {location_name}).")
                logging.error(f"Status code: {response.status}")
                logging.error(await response.text())
                return {"mutation": mutation, "data": None, "status_code": response.status, "error_details": await response.text()}

    async def fetch_mutation_counts(
            self, 
            mutations: List[str], 
            mutation_type: str, 
            date_range: Tuple[datetime, datetime], 
            location_name: Optional[str] = None
            ) -> List[dict[str, Any]]:
        """
        Fetches the mutation counts for a list of mutations, specifying their type and optional location.
        """
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_sample_aggregated(session, m, mutation_type, date_range, location_name) for m in mutations]
            return await asyncio.gather(*tasks)
        

    def _get_symbols_for_mutation_type(self, mutation_type: str) -> List[str]:
        """Returns the list of symbols (amino acids or nucleotides) for the given mutation type."""
        if mutation_type == "aminoAcid":
            return ["A", "C", "D", "E", "F", "G", "H", "I", "K", 
                    "L", "M", "N", "P", "Q", "R", "S", "T", 
                    "V", "W", "Y"]
        elif mutation_type == "nucleotide":
            return ['A', 'T', 'C', 'G']
        else:
            raise ValueError(f"Unknown mutation type: {mutation_type}")

    async def _fetch_coverage_for_mutation(
            self, 
            session: aiohttp.ClientSession,
            mutation: str,
            mutation_type: str,
            date_range: Tuple[datetime, datetime],
            location_name: Optional[str]
        ) -> Tuple[dict[str, int], dict[str, dict]]:
        """
        Fetches coverage data for all possible symbols at a mutation position.
        Returns (coverage_data, stratified_results).
        """
        symbols = self._get_symbols_for_mutation_type(mutation_type)
        mutation_base = mutation[:-1]  # Everything except the last character
        
        # Fetch data for all possible symbols at this position
        coverage_tasks = [
            self.fetch_sample_aggregated(session, f"{mutation_base}{symbol}", mutation_type, date_range, location_name)
            for symbol in symbols
        ]
        coverage_results = await asyncio.gather(*coverage_tasks)

        # Parse coverage_results to extract total counts for each symbol
        coverage_data = {
            symbol: sum(entry['count'] for entry in item['data']) if item['data'] else 0
            for symbol, item in zip(symbols, coverage_results)
        }

        # Stratify results by sampling_date
        stratified_results = {}
        for symbol, item in zip(symbols, coverage_results):
            if item['data']:
                for entry in item['data']:
                    date = entry['sampling_date']
                    count = entry['count']
                    if date not in stratified_results:
                        stratified_results[date] = {"counts": {s: 0 for s in symbols}, "coverage": 0}
                    stratified_results[date]["counts"][symbol] += count
                    stratified_results[date]["coverage"] += count

        return coverage_data, stratified_results

    def _calculate_mutation_result(
            self, 
            mutation: str, 
            coverage_data: dict[str, int], 
            stratified_results: dict[str, dict]
        ) -> dict[str, Any]:
        """
        Calculates the final result for a mutation including overall and stratified statistics.
        """
        target_symbol = mutation[-1]
        total_coverage = sum(coverage_data.values())
        frequency = coverage_data.get(target_symbol, 0) / total_coverage if total_coverage > 0 else 0

        # Calculate frequency for the target symbol on each date
        for date, data in stratified_results.items():
            data["frequency"] = data["counts"].get(target_symbol, 0) / data["coverage"] if data["coverage"] > 0 else 0

        # Build stratified data with proper NA handling
        stratified_data = [
            {
                "sampling_date": date,
                "coverage": data["coverage"],
                "frequency": data["frequency"] if data["coverage"] > 0 else "NA",
                "count": data["counts"].get(target_symbol, 0) if data["coverage"] > 0 else "NA"
            }
            for date, data in stratified_results.items()
        ]

        return {
            "mutation": mutation,
            "coverage": total_coverage,
            "frequency": frequency,
            "counts": coverage_data,
            "stratified": stratified_data
        }

    async def fetch_mutation_counts_and_coverage(
            self, 
            mutations: List[str], 
            mutation_type: str, 
            date_range: Tuple[datetime, datetime], 
            location_name: Optional[str] = None
        ) -> List[dict[str, Any]]:
        """
        Fetches the mutation counts and coverage for a list of mutations, specifying their type and optional location.

        Note Amino Acid mutations require gene:change name "ORF1a:V3449I" while nucleotide mutations can be in the form "A123T".
        """
        if mutation_type not in ["nucleotide", "aminoAcid"]:
            logging.error(f"Unknown mutation type: {mutation_type}")
            raise NotImplementedError(f"Unknown mutation type: {mutation_type}")
        
        async with aiohttp.ClientSession() as session:
            combined_results = []

            for mutation in mutations:
                # Fetch coverage data for all possible symbols at this position
                coverage_data, stratified_results = await self._fetch_coverage_for_mutation(
                    session, mutation, mutation_type, date_range, location_name
                )
                
                # Calculate and append the result for this mutation
                mutation_result = self._calculate_mutation_result(mutation, coverage_data, stratified_results)
                combined_results.append(mutation_result)

            return combined_results
        
    
    def fetch_counts_and_coverage_3D_df_nuc(self, mutations, date_range, location_name) -> pd.DataFrame:
        """Fetches mutation counts, coverage, and frequency for a list of nucleotide mutations over a date range.

        Args:
            mutations (list): List of nucleotide mutations to fetch data for.
            date_range (tuple): Tuple containing start and end dates for the data range.

        Returns:
            pd.DataFrame: A MultiIndex DataFrame with mutation and sampling_date as the index, and count, coverage, and frequency as columns.
        """
        mutation_type = "nucleotide"
        all_data = asyncio.run(self.fetch_mutation_counts_and_coverage(mutations, mutation_type, date_range, location_name))

        # Flatten the data into a list of records
        records = []
        for mutation_data in all_data:
            mutation = mutation_data["mutation"]
            for stratified in mutation_data["stratified"]:
                records.append({
                    "mutation": mutation,
                    "sampling_date": stratified["sampling_date"],
                    "count": stratified["count"],
                    "coverage": stratified["coverage"],
                    "frequency": stratified["frequency"]
                })

        # Create a DataFrame from the records
        df = pd.DataFrame(records)

        # Set MultiIndex with mutation and sampling_date
        df.set_index(["mutation", "sampling_date"], inplace=True)

        # Return the DataFrame
        return df
