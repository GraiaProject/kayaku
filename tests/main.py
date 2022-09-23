def reset_kayaku():
    import kayaku.domain
    from kayaku.domain import _Registry, domain_map, file_map

    kayaku.domain._reg = _Registry()
    domain_map.clear()
    file_map.clear()
