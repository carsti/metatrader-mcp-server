from fastapi import APIRouter, HTTPException, Request, Query
from typing import List, Dict, Any, Optional
from datetime import datetime
# Removed unused import of pandas (pd)
from metatrader_client.exceptions import ConnectionError as MT5ConnectionError

router = APIRouter()

GROUP_DESCRIPTION = (
    "Row grouping, applied only when both symbol_name and timeframe have more "
    "than one value: 'timeframe' blocks by timeframe then symbol, 'symbol' "
    "blocks by symbol then timeframe, 'none' (default) merges everything into a "
    "single stream ordered by time."
)


def candles_payload(df) -> Dict[str, Any]:
    """Shape a candle DataFrame into the endpoint response.

    Pairs that could not be retrieved are reported alongside the data rather
    than failing the whole request.

    Input:
        df: DataFrame returned by a candle client operation, or None.

    Response:
        Dict[str, Any]: {'data': list of candle records, 'errors': list of
        {'symbol', 'timeframe', 'error'} for the pairs that failed, 'truncated':
        list of {'symbol', 'timeframe', 'returned', 'available'} for the pairs
        that had more candles than the limit allowed}.
    """
    attrs = getattr(df, "attrs", {})
    data = [] if df is None or df.empty else df.to_dict(orient="records")
    return {
        "data": data,
        "errors": list(attrs.get("errors") or []),
        "truncated": list(attrs.get("truncated") or []),
    }


@router.get("/candles/latest", response_model=Dict[str, Any])
async def candles_latest(
    request: Request,
    symbol_name: List[str] = Query(..., description="Symbol name, repeatable, e.g., 'EURUSD'"),
    timeframe: List[str] = Query(..., description="Timeframe, repeatable, e.g., 'M1', 'H1'"),
    count: int = Query(100, description="Number of candles to retrieve per symbol/timeframe pair"),
    group: Optional[str] = Query(None, description=GROUP_DESCRIPTION),
):
    """Fetch the latest N candles for one or more symbols and timeframes.

    Input:
        symbol_name (List[str]): One or more symbols, e.g., 'EURUSD'.
        timeframe (List[str]): One or more timeframes, e.g., 'M1', 'H1'.
        count (int): Number of candles per pair (default=100).
        group (Optional[str]): 'timeframe', 'symbol' or 'none' (default='none').

    Response:
        Dict[str, Any]: {'data': candle records with keys 'time', 'open', 'high',
        'low', 'close', 'volume' plus 'symbol'/'timeframe' for the dimensions
        that vary; 'errors': the pairs that could not be retrieved}.
    """
    client = request.app.state.client
    try:
        df = client.market.get_candles_latest(
            symbol_name=symbol_name,
            timeframe=timeframe,
            count=count,
            group=group,
        )
        return candles_payload(df)
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e:  # invalid group, empty symbol list, bad timeframe
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/candles/date", response_model=Dict[str, Any])
async def get_candles_by_date_endpoint( # Choose a descriptive name
    request: Request,
    symbol_name: List[str] = Query(..., description="Symbol name, repeatable, e.g., 'EURUSD'"),
    timeframe: List[str] = Query(..., description="Timeframe, repeatable, e.g., 'M1', 'H1'"),
    date_from: datetime = Query(..., description="Start date and time (ISO 8601 format, e.g., 2023-01-01T00:00:00)"),
    date_to: datetime = Query(..., description="End date and time (ISO 8601 format, e.g., 2023-01-02T23:59:59)"),
    group: Optional[str] = Query(None, description=GROUP_DESCRIPTION),
    limit: int = Query(100, ge=1, description="Maximum candles per symbol/timeframe pair, most recent first"),
):
    """Fetch candles for one or more symbols and timeframes over a date range.

    Input:
        symbol_name (List[str]): One or more symbols, e.g., 'EURUSD'.
        timeframe (List[str]): One or more timeframes, e.g., 'M1', 'H1'.
        date_from (datetime): Start date and time for candles.
        date_to (datetime): End date and time for candles.
        group (Optional[str]): 'timeframe', 'symbol' or 'none' (default='none').

    Response:
        Dict[str, Any]: {'data': candle records with keys 'time', 'open', 'high',
        'low', 'close', 'volume' plus 'symbol'/'timeframe' for the dimensions
        that vary; 'errors': the pairs that could not be retrieved}.
    """
    client = request.app.state.client
    try:
        df = client.market.get_candles_by_date(
            symbol_name=symbol_name,
            timeframe=timeframe,
            from_date=date_from,
            to_date=date_to,
            group=group,
            limit=limit,
        )
        return candles_payload(df)
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except ValueError as e: # Catch potential ValueError from date parsing or client logic
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log the exception for debugging
        # logger.error(f"Error fetching candles for {symbol_name} by date: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching candles by date for {symbol_name}: {str(e)}")

@router.get("/symbol/info/{symbol_name}", response_model=Dict[str, Any])
async def get_symbol_info_endpoint( # Choose a descriptive name like get_symbol_info_route or symbol_info
    request: Request,
    symbol_name: str, # Path parameter
    full: bool = Query(False, description="Return every field the broker exposes instead of the trading subset"),
):
    """Get detailed information for a specific symbol.

    Input:
        symbol_name (str): The trading instrument symbol (e.g., "EURUSD").

    Response:
        Dict[str, Any]: A dictionary containing various details about the symbol.
                        The exact fields depend on the MetaTrader 5 platform's response
                        for `symbol_info()`.
    """
    client = request.app.state.client
    try:
        # The client.market.get_symbol_info() function likely returns an object
        # that might not be directly JSON serializable (e.g. MT5SymbolInfo).
        # It might have a ._asdict() method or similar, or you might need to
        # manually convert its fields to a dictionary if it's a custom class.
        # For now, assume it returns a dict or a Pydantic model that FastAPI can handle.
        info = client.market.get_symbol_info(symbol_name=symbol_name, full=full)
        if info is None: # Or however the client function indicates "not found"
            raise HTTPException(status_code=404, detail=f"Symbol {symbol_name} not found or no info available.")
        # If 'info' is an object with attributes, convert to dict:
        # Example: if hasattr(info, '_asdict'): info = info._asdict()
        # Or if it's a Pydantic model, FastAPI handles it.
        # If it's a simple class, you might need: info = info.__dict__ or vars(info)
        # For now, let's assume it's directly returnable or a Pydantic model.
        return info
    except HTTPException:
        # Do not let the catch-all below rewrite the 404 above into a 500.
        raise
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    # Specific exception for symbol not found if your client raises one
    # except SymbolNotFoundError as e: # Replace with actual exception if available
    #     raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Log the exception for debugging
        # logger.error(f"Error fetching symbol info for {symbol_name}: {e}")
        raise HTTPException(status_code=500, detail=f"An error occurred while fetching info for {symbol_name}: {str(e)}")

@router.get("/price/{symbol_name}", response_model=Dict[str, Any])
async def symbol_price(
    request: Request,
    symbol_name: str,
    query_symbol_name: Optional[str] = Query(None, alias="symbol_name")
):
    """Get the latest price and tick data for a symbol.

    Input:
        symbol_name (str): The symbol to query (path parameter).
        query_symbol_name (Optional[str]): The symbol to query (query parameter, fallback).

    Response:
        Dict[str, Any]: {'bid': float, 'ask': float, 'last': float, 'volume': int, 'time': datetime}.
    """
    client = request.app.state.client
    # Use path parameter if it's not the literal '{symbol_name}', otherwise use query parameter
    actual_symbol_name = symbol_name if symbol_name != "{symbol_name}" else query_symbol_name
    
    if not actual_symbol_name:
        raise HTTPException(status_code=400, detail="Symbol name must be provided")
    
    try:
        return client.market.get_symbol_price(symbol_name=actual_symbol_name)
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/price", response_model=Dict[str, Any])
async def symbol_price_query(
    request: Request,
    symbol_name: str = Query(..., description="Symbol name, e.g., 'EURUSD'")
):
    """Get the latest price and tick data for a symbol using query parameter.

    Input:
        symbol_name (str): The symbol to query.

    Response:
        Dict[str, Any]: {'bid': float, 'ask': float, 'last': float, 'volume': int, 'time': datetime}.
    """
    client = request.app.state.client
    try:
        return client.market.get_symbol_price(symbol_name=symbol_name)
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols", response_model=List[str])
async def all_symbols(request: Request):
    """Get a list of all available market symbols.

    Input:
        None

    Response:
        List[str]: List of symbol names.
    """
    client = request.app.state.client
    try:
        return client.market.get_symbols()
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/symbols/filter", response_model=List[str])
async def filter_symbols(
    request: Request,
    group: Optional[str] = Query(None, description="Filter pattern, e.g., '*USD*'")
):
    """Get a list of all available market symbols, optionally filtered by group.

    Input:
        group (Optional[str]): Filter pattern, e.g., '*USD*'.

    Response:
        List[str]: List of symbol names.
    """
    client = request.app.state.client
    try:
        return client.market.get_symbols(group=group)
    except MT5ConnectionError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
